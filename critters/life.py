
from critters import genetics
from critters import neural
from critters import morph
import networkx as nx
from critters.utils import flatten, cached
from critters.physics import objects
from critters.physics.simulationEnvironment import SimulationEnvironment
import datetime
import pickle

class Critter(genetics.Genotype):
    
    def __init__(self, numSensors=6, morphology=None, neuralNet=None):
        self.numSensors = numSensors
        self.morphology = morphology or morph.randomMorphology(6)
        self.neuralNet = neuralNet or \
                         neural.randomNeuralNetwork(numSensors, 10, 5)
    
    @property
    @cached
    def phenotype(self):
        return ReifiedCreature(self.morphology.expand(),
                               self.neuralNet, self.numSensors)
                               
    def mutate(self):
        newNN = self.neuralNet.mutate()
        newMorph = self.morphology.mutate()
        return Critter(self.numSensors, newMorph, newNN)
        
    def crossover(self, other):
        newNN = self.neuralNet.crossover(other.neuralNet)[0]
        newMorph = self.morphology.crossover(other.morphology)[0]
        return Critter(self.numSensors, newMorph, newNN)
    
class ReifiedCreature(object):
    
    def __init__(self, morphology, neuralNet, numSensors):
        self.morphology = morphology
        self.neuralNet = neuralNet
        self.numSensors = numSensors
                          
        self._calculateBodyParts()
        self._calculateConnections()
        self._conformNeuralNet()
        self.hinges = None#filled in when buildPhysicsObject() is invoked
        self.rects = None #filled in when buildPhysicsObject() is invoked
        
    def clear(self):
        self.neuralNet.clear()
        
    def think(self, inputs, dt):
        actuatorValues = self.neuralNet.process(inputs, dt)
        return dict(zip(self.actuators, actuatorValues))
        
    def _calculateBodyParts(self):
        self.bodyParts = self.morphology.nodes()
        
    def _calculateConnections(self):
        self.connections = [data['connection'] for _, _, data in 
                            self.morphology.edges_iter(data=True)]
        
        self.actuators = flatten([connection.actuators for connection in
                                  self.connections])
    
    def _conformNeuralNet(self):
        self.neuralNet.conform(self.numSensors, len(self.actuators))
        
    def _getConnections(self, bodyPart):
        return [data['connection'] for _, _, data in 
                self.morphology.edges_iter(bodyPart, data=True)]
                
    def _getAdjacentWithConnection(self, bodyPart):
        for connection in self._getConnections(bodyPart):
            for other in connection.nodes:
                if other is not bodyPart:
                    yield other, connection
                    break
        
    def buildPhysicsObject(self):
        def createRect(bodyPart):
            return objects.Rect((0.0, 0.0), bodyPart.dimensions, 0.0, 1, 0.5)
        
        def createHinge(connection, r1, r2):
            def positionToLocal(rect, position):
                vertex = int(position) % 4
                r = position - vertex
                
                x = rect.size[0]/2.0
                y = rect.size[1]/2.0
                
                if vertex == 0:
                    y = 2*r*y - y
                elif vertex == 1:
                    x = x - 2*r*x
                elif vertex == 2:
                    x *= -1
                    y = y - 2*r*y
                elif vertex == 3:
                    y *= -1
                    x = 2*r*x - x
                else:
                    assert False
                
                return x, y
            
            return objects.Hinge(
                    r1, positionToLocal(r1, connection.locations[0]), 
                    r2, positionToLocal(r2, connection.locations[1]))
        
        try:
            root = next(self.morphology.nodes_iter())
        except StopIteration:
            print "Empty morphology"
            return [], []
        
        rects = {}
        hinges = []

        for prev, node in nx.bfs_edges(self.morphology, root):
            for part in (prev, node):
                if part not in rects:
                    rects[part] = createRect(part)

            connection = self.morphology.get_edge_data(prev, node)['connection']
            hinge = createHinge(connection, rects[prev], rects[node])
            hinges.append(hinge)
            
            
            prevGlobal = rects[prev].position
            if rects[prev] == hinge.physObj1:                
                prevLocal = hinge.local1
                otherLocal = hinge.local2
            elif rects[prev] == hinge.physObj2:
                prevLocal = hinge.local2
                otherLocal = hinge.local1
            else:
                raise ValueError, "Neither check for equality with physObj worked"
            
            otherGlobalx = prevGlobal[0] + prevLocal[0] - otherLocal[0] 
            otherGlobaly = prevGlobal[1] + prevLocal[1] - otherLocal[1]
            
            jointLoc1 = (prevGlobal[0] + prevLocal[0],prevGlobal[1] + prevLocal[1]) #sanity check
            jointLoc2 = (otherGlobalx + otherLocal[0],otherGlobaly+ otherLocal[1]) #calculate relative to both global locs
            
            xDif = abs(jointLoc1[0]-jointLoc2[0])
            yDif = abs(jointLoc1[1]-jointLoc2[1])
            if yDif > 0.1 or xDif > 0.1: #we may need to change this value later
                raise "The joint should be in the same position when calculated from either object..."
                
            rects[node].position = (otherGlobalx,otherGlobaly)
            hinge.globalLoc = jointLoc1

        self.rects = rects.values()
        self.hinges = hinges
        
        return self.rects, self.hinges

class DistanceCompetition(genetics.IndividualCompetition):
    
    MIN_TIME = 10.0
    MIN_SCORE = 20.0
    MAX_TIME = 30.0
    
    MIN_FITNESS = 0.000001
    RECTS_THRESHOLD = 8.0

    def _doCalculation(self,individual):       
        simEnv = SimulationEnvironment(vis=False)
        failure = individual, self.MIN_FITNESS
        
        try:
            body = simEnv.addCreature(individual)
        except RuntimeError as e:
            print e
            return failure
        
        if not body: return failure
        
        before = simEnv.getMeanX(body)
        
        def calculateScore():
            score = simEnv.getMeanX(body) - before
            
            rects, _ = body
            if len(rects) > self.RECTS_THRESHOLD:
                score /= len(rects) - self.RECTS_THRESHOLD
            if simEnv.isBelowGround(body):
                score = 0
            
            return max(self.MIN_FITNESS, score)
        
        def check():
            return calculateScore() >= self.MIN_SCORE
        
        simEnv.simulate(timeToRun=self.MAX_TIME, check=(self.MIN_TIME, check))
        
        return individual, calculateScore()

if __name__ == '__main__':
    import os
    _outFolderName = os.path.join(os.getcwd(),'output')
    
    outFolderName = _outFolderName
    i = 0
    while os.path.exists(outFolderName):
        i += 1
        outFolderName = _outFolderName + "(%d)"%i 

    if i == 0:
        outFileName = os.path.join(outFolderName,'output.csv')
     
    outFileName = os.path.join(outFolderName,'output(%d).csv'%i)
    print 'Saving output to :' + outFolderName
    print 'Saving output to :' + outFileName
    os.mkdir(outFolderName)
    outFile = open(outFileName,'w')
   
    reproduction = genetics.MatedReproduction(Critter)
    evo = genetics.Evolution(reproduction, DistanceCompetition(), 300)
    evo.populate()

    def onGeneration(latest, n):
        myList = [str(n), str(latest.maxFitness), str(latest.meanFitness), str(latest.size), str(datetime.datetime.now().time())]
        myList.extend([str(round(f,5)) for f in latest.scores.values()])
        outFile.write(" , ".join(myList) + "\n")
        print 'Generation ',n, 'was written to disk at', str(datetime.datetime.now().time())
        print "N=%d, max fitness=%.3f, mean fitness=%.3f" % (n, latest.maxFitness, latest.meanFitness)
        
        pickle.dump(latest.bestPhenotype, open( os.path.join(os.getcwd(), outFolderName+'/max_%d'%n), "wb" ))
        
    try:    
        evo.run(maxSteps=150, onGeneration=onGeneration)
    except KeyboardInterrupt:
        print "caught interrupt, writing to disk"
        outFile.flush()
        
    print("done")






