#-------------------------------------

import math
import sys
import pdb
from SketchFramework import SketchGUI

from Utils import Logger
from Utils import GeomUtils
from SketchFramework.Point import Point
from SketchFramework.Stroke import Stroke
from SketchFramework.Board import BoardObserver, BoardSingleton
from SketchFramework.Annotation import Annotation, AnnotatableObject
from Observers import ObserverBase




class SplitStrokeAnnotation(Annotation):
    
    def __init__(self, strokelist = []):
        self.Points = []
        for s in strokelist:
            self.mergeStroke(s)

    def reverseDirection(self):
        self.Points.reverse()

    def mergeStroke(self, stroke, mergeBefore = False ):
        """
        sp1 = stroke.Points[0]
        sp2 = stroke.Points[-1]
        if len(self.Points) > 0:
            ep2 = self.Points[-1]
            ep2_sp1dist = GeomUtils.pointDistanceSquared(ep2.X, ep2.Y, sp1.X, sp1.Y)
            ep2_sp2dist = GeomUtils.pointDistanceSquared(ep2.X, ep2.Y, sp2.X, sp2.Y)

            ep1 = self.Points[0]
            ep1_sp1dist = GeomUtils.pointDistanceSquared(ep1.X, ep1.Y, sp1.X, sp1.Y)
            ep1_sp2dist = GeomUtils.pointDistanceSquared(ep1.X, ep1.Y, sp2.X, sp2.Y)
            mindist = min([ep2_sp1dist, ep2_sp2dist, ep1_sp2dist, ep1_sp1dist])

            if   mindist == ep1_sp1dist: # Head to head
                newPts = reversed(stroke.Points)
                newPts.extend(self.Points)
                self.Points = newPts

            elif mindist == ep1_sp2dist: # head to tail
                newPts = stroke.Points
                newPts.extend(self.Points)
                self.Points = newPts
            
            elif mindist == ep2_sp1dist: #tail to head
                self.Points.extend(stroke.Points)

            elif mindist == ep2_sp2dist: #tail to tail
                newPts = reversed(stroke.Points)
                self.Points.extend(newPts)
        """
        if mergeBefore:
            self.Points = stroke.Points + self.Points
        else:
            self.Points.extend(stroke.Points)
            
        
                

#-------------------------------------
ss_logger = Logger.getLogger("SplitStrokeMarker", Logger.DEBUG)

class SplitStrokeMarker( ObserverBase.Collector ):

    def __init__( self ):
        # this will register everything with the board, and we will get the proper notifications
        BoardSingleton().RegisterForStroke(self)
        ObserverBase.Collector.__init__( self, [], SplitStrokeAnnotation)

    def onStrokeAdded(self, stroke):
        ss_logger.debug("Stroke Added")
        splitStrokAnno = SplitStrokeAnnotation(strokelist=[stroke])
        BoardSingleton().AnnotateStrokes([stroke], splitStrokAnno)

    def collectionFromItem( self, strokes, anno ):
        return anno

    def mergeCollections( self, from_anno, to_anno ):
        "merge from_anno into to_anno if they point to each other"
        offsetDist = 5
        merged = False

        #How far into the strokes do we go to determine their pointing direction?
        from_offset = min (offsetDist, len(from_anno.Points))
        to_offset = min (offsetDist, len(to_anno.Points))

        #Get the pairs for each "stroke's" head and tail lines
        from_headpair = (from_anno.Points[from_offset], from_anno.Points[0])
        to_headpair = (to_anno.Points[to_offset], to_anno.Points[0])

        from_tailpair = (from_anno.Points[ -from_offset], from_anno.Points[-1])
        to_tailpair = (to_anno.Points[ -to_offset], to_anno.Points[-1])
        

        if linesPointAtEachother(from_headpair, to_tailpair):
            #From_anno head links to to_anno's tail
            to_anno.mergeStroke(from_anno, mergeBefore = False)
            merged = True

        elif linesPointAtEachother(from_tailpair, to_headpair):
            #From_anno tail links to to_anno's head
            to_anno.mergeStroke(from_anno, mergeBefore = True)
            merged = True

        elif linesPointAtEachother(from_headpair, to_headpair):
            #From_anno head links to to_anno's head
            to_anno.reverseDirection()
            to_anno.mergeStroke(from_anno, mergeBefore = False)
            merged = True

        elif linesPointAtEachother(from_tailpair, to_tailpair):
            to_anno.reverseDirection()
            to_anno.mergeStroke(from_anno, mergeBefore = True)
            merged = True

        return merged
    def onStrokeRemoved(self, stroke):
        allStrokes = set([])


def linesPointAtEachother(linepair1, linepair2):
    ep1 = linepair1[1]
    ep2 = linepair2[1]
    pointsToRadius = max(5, 0.26 * GeomUtils.pointDistance(ep1.X, ep1.Y, ep2.X, ep2.Y) ) #Span out the valid radius at about 30 degrees
    l1_to_l2 = GeomUtils.linePointsTowards(linepair1[0], linepair1[1], linepair2[1], pointsToRadius)
    l2_to_l1 = GeomUtils.linePointsTowards(linepair2[0], linepair2[1], linepair1[1], pointsToRadius)
    return (l1_to_l2 and l2_to_l1)
    


#-------------------------------------

class RaceTrackAnnotation(Annotation):
    def __init__(self, rightwalls = [], leftwalls = []):
        Annotation.__init__(self)
        self.rightwalls = rightwalls # A list of strokes making up the right walls of the track
        self.leftwalls = leftwalls #A list of strokes making up the left walls

        self.centerline = None #Stroke for the centerline
        self.rebuildCenterline()
    def rebuildCenterline(self):
        pass

#-------------------------------------

rtv_logger = Logger.getLogger("RaceTrackVisualizer", Logger.DEBUG)
class RaceTrackVisualizer( ObserverBase.Visualizer ):
    "Watches for DiGraph annotations, draws them"
    def __init__(self):
        ObserverBase.Visualizer.__init__( self, RaceTrackAnnotation )

    def drawAnno( self, a ):
        right_color = "#CF0000"
        left_color = "#0000C0"
        for wall in a.rightwalls: #Strokes
            rtv_logger.debug("Drawing right wall")
            wall = GeomUtils.strokeSmooth(wall, width = 6, preserveEnds = True)
            SketchGUI.drawStroke(wall, width = 2, color = right_color)
        for wall in a.leftwalls: #Strokes
            rtv_logger.debug("Drawing left wall")
            SketchGUI.drawStroke(wall, width = 2, color = left_color)


#-------------------------------------

rtm_logger = Logger.getLogger('RacetrackObserver', Logger.WARN )
class RaceTrackMarker( BoardObserver ):
    def __init__(self):
        self.maybeWalls = set([]) #A set of strokes things that aren't part of a racetrack yet
        self.wallInfo = {} #A dict indexed by  strokes for useful info on partial walls
        BoardSingleton().RegisterForStroke( self )

    def onStrokeAdded( self, stroke ):
        #If it's a closed figure, it is its own wall
        rtm_logger.debug("Stroke Added")
        newWallDict = {'closed': False, 'matches': {}}
        ep1 = stroke.Points[0]
        ep2 = stroke.Points[-1]
        strokeLen = GeomUtils.strokeLength(stroke)

        addToWalls = True
        if GeomUtils.pointDistanceSquared(ep1.X, ep1.Y, ep2.X, ep2.Y) < (strokeLen  * 0.05) ** 2:
            rtm_logger.debug("Closed stroke")
            newWallDict['closed'] = True

        rtm_logger.debug("Adding stroke as possible future wall")
        self.wallInfo[stroke] = newWallDict
        #self.linkStrokesTogether()

        for testStroke, wallDict in self.wallInfo.items():
            gran = min(len(stroke.Points), len(testStroke.Points))
            if wallDict['closed'] and GeomUtils.strokeContainsStroke(testStroke, stroke, granularity = gran):
                outStk = testStroke
                inStk = stroke
            elif newWallDict['closed'] and GeomUtils.strokeContainsStroke(stroke, testStroke, granularity = gran):
                outStk = stroke
                inStk = testStroke
            else:
                continue

            rtm_logger.debug("Found containment with another stroke")
            rtAnno = RaceTrackAnnotation(rightwalls = [outStk], leftwalls = [inStk]) 
            BoardSingleton().AnnotateStrokes([stroke, testStroke], rtAnno)
            del(self.wallInfo[testStroke])
            addToWalls = False
            break


    def linkStrokesTogether(self):
        def allPairs(xlist, ylist):
            for x in xlist:
                for y in ylist:
                    yield ( x, y )
        for w1, w1Dict in self.wallInfo.items():
            ep11, ep12 = w1.Points[0], w1.Points[-1]
            self.wallInfo[w1]['matches'] = {}

            for w2 , w2Dict in self.wallInfo.items():
                if w2 == w1 or w2 in self.wallInfo[w1]['matches']:
                    continue

                ep21, ep22 = w2.Points[0], w2.Points[-1]
                bestMatch = {'stroke': None, 'dist': None, 'from_pt': None, 'to_pt': None}
                for pair in allPairs([ep11, ep12], [ep21, ep22]):
                    dist = GeomUtils.pointDistance(pair[0].X, pair[0].Y, pair[1].X, pair[1].Y)
                    if bestMatch['dist'] is None or bestMatch['dist'] > dist:
                        bestMatch = {'dist': dist, 'from_pt': pair[0], 'to_pt': pair[1]}

                self.wallInfo[w1]['matches'][w2] = bestMatch
                self.wallInfo[w2]['matches'][w1] = dict(bestMatch)
            #endfor w2, w2Dict
        #endfor w1, w1Dict

        #Link together partial walls
        wallStack = list(self.wallInfo.keys())
        wallStrokes = {}
        curWall = None
        start = None
        while len(wallStack) > 0:
            if curWall == None:
                curWall = wallStack.pop()
            bestMatch = None
            bestDist = None
            for matchStk, matchDict in self.wallInfo[curWall]['matches'].items():
                if matchStk in wallStack and (bestMatch == None or matchDict['dist'] < bestDist):
                    bestDist = matchDict['dist']
                    bestMatch = matchStk

            if bestMatch != None:
                curWall = bestMatch
                wallStack.remove(bestMatch)
            


        for stk, stkDict in self.wallInfo.items():
            rtm_logger.debug( "%s: " % (stk))
            for match, mdict in stkDict['matches'].items():
                rtm_logger.debug( "    %s: %s " % (match, mdict['dist']))
                
    def onStrokeRemoved(self, stroke):
        rtm_logger.debug("stroke removed")
        otherStrokes = set([stroke])

        if stroke in self.wallInfo:
            del(self.wallInfo[stroke])

    	for anno in stroke.findAnnotations(RaceTrackAnnotation):
            otherStrokes.update(anno.Strokes)
            BoardSingleton().RemoveAnnotation(anno)

        otherStrokes.remove(stroke)

        for stk in otherStrokes:
            assert stk != stroke
            self.onStrokeAdded(stk)

            

