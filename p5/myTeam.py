# myTeam.py
# ---------
# Licensing Information: Please do not distribute or publish solutions to this
# project. You are free to use and extend these projects for educational
# purposes. The Pacman AI projects were developed at UC Berkeley, primarily by
# John DeNero (denero@cs.berkeley.edu) and Dan Klein (klein@cs.berkeley.edu).
# For more info, see http://inst.eecs.berkeley.edu/~cs188/sp09/pacman.html

from captureAgents import CaptureAgent
import random, time, util
from game import Directions
from util import nearestPoint
import game

#################
# Team creation #
#################

def createTeam(firstIndex, secondIndex, isRed,
               first = 'OffensiveAgent', second = 'DefensiveAgent'):
  """
  This function should return a list of two agents that will form the
  team, initialized using firstIndex and secondIndex as their agent
  index numbers.  isRed is True if the red team is being created, and
  will be False if the blue team is being created.

  As a potentially helpful development aid, this function can take
  additional string-valued keyword arguments ("first" and "second" are
  such arguments in the case of this function), which will come from
  the --redOpts and --blueOpts command-line arguments to capture.py.
  For the nightly contest, however, your team will be created without
  any extra arguments, so you should make sure that the default
  behavior is what you want for the nightly contest.
  """
  agent1 = eval(first)(firstIndex)
  agent2 = eval(second)(secondIndex)
  globalModels = []

  agent1.setModel(globalModels)
  agent2.setModel(globalModels)

  # The following line is an example only; feel free to change it.
  return [agent1, agent2]

##########
# Agents #
##########

from distanceCalculator import Distancer

 
class BlockerAgent(CaptureAgent):
  
  def registerInitialState(self, gameState):
   
    CaptureAgent.registerInitialState(self, gameState)
    self.onGuard = False
    
  def chooseAction(self, gameState):
    
    actions = gameState.getLegalActions(self.index)
    default = 'Stop'
    capsules = CaptureAgent.getCapsulesYouAreDefending(self, gameState)
    
    if(capsules):
      capsuleToGoTo = capsules[0]
      myPos = gameState.getAgentPosition(self.index)
      
      if(myPos != capsuleToGoTo and not self.onGuard):
        for action in actions: 
          newState = self.getSuccessor(gameState, action)
          newDis = CaptureAgent.getMazeDistance(self, newState.getAgentState(self.index).getPosition(),capsuleToGoTo);
          currentDis = CaptureAgent.getMazeDistance(self, myPos,capsuleToGoTo);
          if newDis < currentDis:
              return action
      else:
        if not self.onGuard:
          default = actions[0]
          self.onGuard = True
 
    return default
    
  def getSuccessor(self, gameState, action):
    """
    Finds the next successor which is a grid position (location tuple).
    """
    successor = gameState.generateSuccessor(self.index, action)
    pos = successor.getAgentState(self.index).getPosition()
    if pos != nearestPoint(pos):
      # Only half a grid position was covered
      return successor.generateSuccessor(self.index, action)
    else:
      return successor

class DefensiveAgent(CaptureAgent):
  
  # Initialisation function
  def registerInitialState(self, gameState):
    CaptureAgent.registerInitialState(self, gameState)
    
    # self.globalBeliefs

    # Boolean representing if the agent currently is powered up
    self.powerUp = False
    # Keeps track of how much time is left on the power up
    self.powerUpTimer = 0
    self.foodLeft = len(self.getFood(gameState).asList())
    self.allLegalPositions = [p for p in gameState.getWalls().asList(False) if p[1] > 1]
    self.inferenceModules = []
    
    # Create an ExactInference mod for each opponent
    for index in self.getOpponents(gameState):
      infmodel = ExactInference(gameState, self.index, index)
      self.inferenceModules.append(infmodel)
    
    self.firstMove = True
    
    # Initialise opponent beliefs
    self.ghostBeliefs = [inf.getBeliefDistribution() for inf in self.inferenceModules]
    
    # Changes the weighting on score based on what team the agents on,
    # by default the score is the red teams score
    if self.red:
      self.scoreWeight = 500
    else:
      self.scoreWeight = -500
      
  # Choose the best action from the current gamestate based on features 
  def chooseAction(self, gameState):
    
    # Update the beliefs for the opponents
    for index, inf in enumerate(self.inferenceModules): 
      if(len(self.globalBeliefs) < 2):
        self.globalBeliefs.append(inf.getBeliefDistribution())

      if not self.firstMove: inf.elapseTime(gameState, self.globalBeliefs[index])

      self.globalBeliefs[index] = inf.getBeliefDistribution()

      self.firstMove = False
      inf.observe(gameState, self.globalBeliefs[index])

      if(len(self.globalBeliefs) >= 2):
        self.globalBeliefs[index] = inf.getBeliefDistribution()
      self.ghostBeliefs[index] = self.globalBeliefs[index]
      inf.setBeliefDistribution(self.globalBeliefs[index])
    
    # Displays the beliefs on the game board, provides zero actual functionality
    self.displayDistributionsOverPositions(self.globalBeliefs)
    
    # Build up scores for each action based on features
    actionScores = util.Counter()
    for action in gameState.getLegalActions(self.index):
      newState = gameState.generateSuccessor(self.index, action)
      actionScores[self.getActionScore(newState, action)] = action
    
    #print(actionScores)
    # Choose the action with the best score
    bestAction = actionScores[max(actionScores)]
    
    # If the action leads to eating a power up, set the powerUp boolean and start the timer
    if gameState.generateSuccessor(self.index,bestAction).getAgentPosition(self.index) in self.getCapsules(gameState):
      self.powerUp = True
      self.powerUpTimer = 80
    
    # Keeps track of how much food is left
    if gameState.generateSuccessor(self.index,bestAction).getAgentPosition(self.index) in self.getFood(gameState).asList():
      self.foodLeft -= 1
    # If the agent is currently powered up, decrement the timer
    if self.powerUp:
      self.powerUpTimer -= 1
    # When the timer reaches zero, reset the boolean value 
    if self.powerUpTimer == 0:
      self.powerUp = False
    
    return bestAction
    
  def getActionScore(self, gameState, action):
    features = self.getFeatures(gameState, action)
    # Get the dot product of the weight and feature vectors
    score = sum([self.getWeights()[i]*features[i] for i in features])
    return score
    
  def getFeatures(self, gameState, action):
    features =  {
      # Go towards the nearest inferred distance
      'inferredGhost': self.getClosestInferredGhost(gameState)[1],
      # This will either be zero (farther than 5 spaces away) or the distance (less than five), if the ghost is scarred this is negated to make it run away
      'nearGhost': self.getNearGhostDistance(gameState) if (not gameState.getAgentState(self.index).scaredTimer) else -self.getNearGhostDistance(gameState),
      # Discourages stopping
      'stop': 1 if action == Directions.STOP else 0,
      # Prevents the defensive agent going to the offensive side
      'offensiveSide': self.getSide(gameState, gameState.getAgentPosition(self.index)),
      # Don't go down an immediate dead end if scared
      'deadEnd': 1 if (gameState.getAgentState(self.index).scaredTimer and self.isDeadEnd(gameState)) else 0
    }
    return features
    
  def getWeights(self):
    return {
      'inferredGhost': -1.0,
      'nearGhost': -1000.0,
      'stop': -1.0,
      'offensiveSide': -100000000.0,
      'deadEnd':-10000.0
    } 
  
  # Returns a 1 if on the offensive side, 0 if own side
  def getSide(self, gameState, pos):
    midpoint = len(gameState.getWalls()[0])
    #print("red: ",self.red," midpoint: ", midpoint , " pos: " ,pos)
    if (self.red):
      return int (pos[0] > midpoint)
    else:
      return int (pos[0] < midpoint)
  
  # Returns true if state is a dead end
  def isDeadEnd(self, gameState):
    return True if len(gameState.getLegalActions(self.index)) == 2 else False
      
  # Returns 0 if no ghosts can be seen (they are farther than 5 spaces away from either agents)
  def getNearGhostDistance(self, gameState):
    # Computes distance to invaders we can see
    enemies = [gameState.getAgentState(i) for i in self.getOpponents(gameState)]
    invaders = [a for a in enemies if a.isPacman and a.getPosition() != None]
    nearest = 0
    if len(invaders) > 0:
      dists = [self.getMazeDistance(gameState.getAgentPosition(self.index), a.getPosition()) for a in invaders]
      nearest = min(dists)
    return nearest
  
  # Returns the (position, distance) of the closest ghost based on the inference modules
  def getClosestInferredGhost(self, gameState):
    probPositions = []
    myPosition = gameState.getAgentPosition(self.index)
    for inf in self.inferenceModules:
      probPositions.append(inf.getBeliefDistribution().argMax())
    distances = map(lambda x: self.getMazeDistance(x, myPosition), probPositions)
    mindistance = min(distances);
    return [probPositions[distances.index(mindistance)], mindistance]
    
  def getSuccessor(self, gameState, action):
    """
    Finds the next successor which is a grid position (location tuple).
    """
    successor = gameState.generateSuccessor(self.index, action)
    pos = successor.getAgentState(self.index).getPosition()
    if pos != nearestPoint(pos):
      # Only half a grid position was covered
      return successor.generateSuccessor(self.index, action)
    else:
      return successor

  def setModel(self, globalModel):
    self.globalBeliefs = globalModel


class OffensiveAgent(CaptureAgent):
  
  def registerInitialState(self, gameState):
    CaptureAgent.registerInitialState(self, gameState)
    self.powerUp = False
    self.powerUpTimer = 0
    self.capsules = self.getCapsules(gameState)
    self.allLegalPositions = [p for p in gameState.getWalls().asList(False) if p[1] > 1]
    self.foodLeft = len(self.getFood(gameState).asList())
    self.inferenceModules = []
    # Create an ExactInference mod for each opponent
    for index in self.getOpponents(gameState):
      infmodel = ExactInference(gameState, self.index, index)
      self.inferenceModules.append(infmodel)
    
    
    self.ghostBeliefs = [belief for belief in self.globalBeliefs]

    self.firstMove = True
    self.ghostBeliefs = [inf.getBeliefDistribution() for inf in self.inferenceModules]

    if self.red:
      self.scoreWeight = 500
    else:
      self.scoreWeight = -500
      
    
  def chooseAction(self, gameState):

    # Update the beliefs for the opponents
    for index, inf in enumerate(self.inferenceModules): 
      if(len(self.globalBeliefs) < 2):
        self.globalBeliefs.append(inf.getBeliefDistribution())

      if not self.firstMove: inf.elapseTime(gameState, self.globalBeliefs[index])
      
      self.globalBeliefs[index] = inf.getBeliefDistribution()

      self.firstMove = False
      inf.observe(gameState, self.globalBeliefs[index])

      if(len(self.globalBeliefs) >= 2):
        self.globalBeliefs[index] = inf.getBeliefDistribution()
      self.ghostBeliefs[index] = self.globalBeliefs[index]
      inf.setBeliefDistribution(self.globalBeliefs[index])
    
    # Displays the beliefs on the game board, provides zero actual functionality
    self.displayDistributionsOverPositions(self.globalBeliefs)

    #build up scores for each action based on features
    self.capsules = self.getCapsules(gameState)

    actionScores = util.Counter()
    for action in gameState.getLegalActions(self.index):
      newState = gameState.generateSuccessor(self.index, action)
      actionScores[self.getActionScore(newState, action)] = action
    
    #choose the action with the best score
    bestAction = actionScores[max(actionScores)]
    
    #if the action leads to eating a power up, set the powerUp boolean
    if gameState.generateSuccessor(self.index,bestAction).getAgentPosition(self.index) in self.getCapsules(gameState):
      self.powerUp = True
      self.powerUpTimer = 80
      #print("POWER UP!")
      
    if gameState.generateSuccessor(self.index,bestAction).getAgentPosition(self.index) in self.getFood(gameState).asList():
      self.foodLeft -= 1
    
    if self.powerUp:
      self.powerUpTimer -= 1
      
    if self.powerUpTimer == 0:
      self.powerUp = False
    
    
    return bestAction
    
  def getActionScore(self, gameState, action):
    features = self.getFeatures(gameState, action)
    score = sum([self.getWeights()[i]*features[i] for i in features])
    return score

  # Returns true if state is a dead end
  def isDeadEnd(self, gameState):
    return True if len(gameState.getLegalActions(self.index)) == 2 else False
    
  def getFeatures(self, gameState, action):
    inferredGhostFeature = 1.0/max(self.getClosestInferredGhost(gameState)[1],.1) if (self.getClosestInferredGhost(gameState)[1] > 4) else 3.0/max(self.getClosestInferredGhost(gameState)[1],0.1)
    features =  {
      # Get distance to nearest food
      'nearestFood':1.0/min(self.getMazeDistance(gameState.getAgentPosition(self.index),p) for p in self.getFood(gameState).asList()),
      # Get distance to nearest powerup
      'nearestPowerUp': 1.0 if len(self.getCapsules(gameState))==0 else 1.0/min(self.getMazeDistance(gameState.getAgentPosition(self.index),p) for p in self.getCapsules(gameState)),
      # Don't go down an immediate dead end if scared
      'deadEnd': 1 if ((not self.powerUp) and self.isDeadEnd(gameState) and self.getNearGhostDistance(gameState) < 3) else 0,
      'score': gameState.getScore(),
      'stop': 1 if action == Directions.STOP else 0,
      'foodEaten': 1.0 if len(self.getFood(gameState).asList()) < self.foodLeft else 0,
      # Go towards the nearest inferred distance
      'inferredGhost':  inferredGhostFeature if (not self.powerUp) else -inferredGhostFeature    
    }
    #print(features)
    return features
    
  def getWeights(self):
    return {
      'nearestFood':2.0,
      'nearestPowerUp': 100.0,
      'score': self.scoreWeight,
      'deadEnd': -100.0,
      'stop': -5.0,
      'foodEaten': 50.0,
      'inferredGhost': -1.0,
    }  
    
  # Returns 0 if no ghosts can be seen (they are farther than 5 spaces away from either agents)
  def getNearGhostDistance(self, gameState):
    # Computes distance to invaders we can see
    enemies = [gameState.getAgentState(i) for i in self.getOpponents(gameState)]
    invaders = [a for a in enemies if a.isPacman and a.getPosition() != None]
    nearest = 0
    if len(invaders) > 0:
      dists = [self.getMazeDistance(gameState.getAgentPosition(self.index), a.getPosition()) for a in invaders]
      nearest = min(dists)
    return nearest
  
  # Returns the (position, distance) of the closest ghost based on the inference modules
  def getClosestInferredGhost(self, gameState):
    probPositions = []
    myPosition = gameState.getAgentPosition(self.index)
    for inf in self.inferenceModules:
      probPositions.append(inf.getBeliefDistribution().argMax())
    distances = map(lambda x: self.getMazeDistance(x, myPosition), probPositions)
    mindistance = min(distances);
    return [probPositions[distances.index(mindistance)], mindistance]
    

  # Returns true if state is a dead end
  def isDeadEnd(self, gameState):
    return True if len(gameState.getLegalActions(self.index)) == 2 else False
  
  def getSuccessor(self, gameState, action):
    """
    Finds the next successor which is a grid position (location tuple).
    """
    successor = gameState.generateSuccessor(self.index, action)
    pos = successor.getAgentState(self.index).getPosition()
    if pos != nearestPoint(pos):
      # Only half a grid position was covered
      return successor.generateSuccessor(self.index, action)
    else:
      return successor

  def setModel(self, globalModel):
    self.globalBeliefs = globalModel
 
from game import Actions
 
class ExactInference:
  
  def __init__(self, gameState, myIndex, enemyIndex):
    "Begin with a uniform distribution over ghost positions."
    self.beliefs = util.Counter()
    self.allLegalPositions = [p for p in gameState.getWalls().asList(False) if p[1] > 1]
    self.initBeliefs();
    self.enemyIndex = enemyIndex
    self.myIndex = myIndex
  
  def observe(self, gameState, globalBeliefs):

    # Get current noisy pos and our agent position
    noisyDistance = gameState.getAgentDistances()[self.enemyIndex]
    exactPos = gameState.getAgentPosition(self.enemyIndex)
    myPosition = gameState.getAgentPosition(self.myIndex)
    # Create new beliefs variable
    newBeliefs = util.Counter()
    
    if(sum(self.beliefs.values()) == 0):
      self.initBeliefs()
      
    # Check if within 5 spaces
    if exactPos:
      newBeliefs[exactPos] = 1.0
    else:
      # Iterate through every legal position
      for p in globalBeliefs:
        # Get the true distance from agent pos -> this pos
        trueDistance = util.manhattanDistance(p, myPosition)
        # Find the probability that this is a noisy position
        prob = gameState.getDistanceProb(trueDistance, noisyDistance) * globalBeliefs[p]
        # Only add position to the new beliefs array if it is noisy
        #if(prob != 0): 
        newBeliefs[p] =  prob

    # Save updated belief locations to instance variable
    newBeliefs.normalize()
    self.beliefs = newBeliefs

  def elapseTime(self, gameState, globalBeliefs):
    newBeliefs = util.Counter()

    # Updates all the possible ghost legal positions for the elapsed state
    possiblePositions = self.getAllPossibleNextPositions(gameState, globalBeliefs);
    
    # Iterates over every position in the current belief
    for oldPos in globalBeliefs:

      # Iterates over each possible move for this position
      if(len(possiblePositions) > 0):
        for legalMovePos in possiblePositions[oldPos]:

          # Add (1/num_moves * old_belief) to the new belief for this legal move
          newBeliefs[legalMovePos] += (1.0/len(possiblePositions[oldPos])) * globalBeliefs[oldPos] #p(t+1, t) = p(t+1 | t) * p(t)
      
    newBeliefs.normalize()   
    self.beliefs = newBeliefs      
  
  # Returns dictionary of (x,y) : [possible moves for x,y] for every self.belief
  def getAllPossibleNextPositions(self, gameState, globalBeliefs):
    possiblePositions = {}
    for pos in globalBeliefs:
      nextPos = Actions.getLegalNeighbors(pos, gameState.getWalls())#[(x+1,y),(x-1,y),(x,y+1),(x,y-1)]

      possiblePositions[pos] = nextPos#filter(lambda x: not gameState.hasWall(x[0],x[1]),nextPos))
    return possiblePositions

  def getPossibleNextPositions(self, gameState, pos):
    return Actions.getLegalNeighbors(pos, gameState.getWalls())

  def getBeliefDistribution(self):
    return self.beliefs

  def setBeliefDistribution(self, beliefs):
    self.beliefs = beliefs

  def initBeliefs(self):
    # Reset beliefs to 1.0 for all legal positions on map
    for p in self.allLegalPositions: self.beliefs[p] = 1.0
    self.beliefs.normalize();
