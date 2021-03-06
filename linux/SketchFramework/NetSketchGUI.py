#!/usr/bin/env python
"""
filename: NetSketchGUI.py

Description:
   This class should control all interface matters. It must export:
       TkSketchGUISingleton
       TkSketchGUI (Class)
          drawLine
          drawCircle
          drawText
   All other functions and interface behavior is up to the GUI designer.
   This implementation listens for MouseDown events and builds strokes to hand off
      to the board system. Upon any event, Redraw is called globally to fetch all 
      board paint objects and display them.
Todo:
   It would be nice if the interface weren't so directly tied to the Tkinter underpinnings.
   I.e., TkSketchGUI is essentially a Tkinter frame object, and must be manipulated similarly.
"""


import pdb
import time
import threading
import Queue
import StringIO
import Image

from xml.etree import ElementTree as ET

from SketchFramework.SketchGUI import _SketchGUI
from SketchFramework.Point import Point
from SketchFramework.Stroke import Stroke
from SketchFramework.Board import BoardSingleton
from SketchFramework.NetworkReceiver import ServerThread
from SketchFramework.strokeout import imageBufferToStrokes, GETNORMWIDTH

from Observers import CircleObserver
from Observers import ArrowObserver
from Observers import DebugObserver
from Observers import TextObserver
from Observers import DiGraphObserver
from Observers import TuringMachineObserver


from Utils.StrokeStorage import StrokeStorage
from Utils import Logger

from Observers.ObserverBase import Animator

# Constants
WIDTH = 1024
HEIGHT = 3 * WIDTH / 4

MID_W = WIDTH/2
MID_H = HEIGHT/2

   
logger = Logger.getLogger("NetSketchGUI", Logger.DEBUG)


class DrawAction(object):
    def __init__(self, action_type):
        self.action_type = action_type
    def xml(self):
        raise NotImplemented

class DrawCircle(DrawAction):
    def __init__(self, x, y, radius, color, fill, width):
        DrawAction.__init__(self, "Circle")
        self.x = x
        self.y = y
        self.radius = radius
        self.color = color
        self.fill = fill
        self.width = width

        self._hash = None

    def __hash__(self):
        if self._hash is None:
            self._hash = 0
            for member in [self.action_type, 
                           self.x, self.y, 
                           self.radius, 
                           self.color, 
                           self.fill, 
                           self.width]:
                self._hash = hash(self._hash + hash(member))
        return self._hash

    def xml(self):
        "Returns an ElementTree of this object"
        root = ET.Element(self.action_type)
        x = ET.SubElement(root, "x")
        x.text = str(self.x)

        y = ET.SubElement(root, "y")
        y.text = str(self.y)

        radius = ET.SubElement(root, "radius")
        radius.text = str(self.radius)

        color = ET.SubElement(root, "color")
        color.text = str(self.color)

        fill = ET.SubElement(root, "fill")
        fill.text = str(self.fill)

        width = ET.SubElement(root, "width")
        width.text = str(self.width)

        return root


class DrawStroke(DrawAction):
    def __init__(self, stroke, width, color):
        DrawAction.__init__(self, "Stroke")
        self.stroke = stroke
        self.width = width
        self.color = color

    def xml(self):
        "Returns an ElementTree of this object"
        root = ET.Element(self.action_type)

        root.attrib['id'] = str(self.stroke.id)
        root.attrib['color'] = str(self.color)
        root.attrib['width'] = str(self.width)

        for i, pt in enumerate(self.stroke.Points):
            pt_el = ET.SubElement(root, "p")
            
            #pt_el.attrib['id'] = str(i)
            pt_el.attrib['x'] = str(pt.X)
            pt_el.attrib['y'] = str(pt.Y)

        return root

class DrawLine(DrawAction):
    def __init__(self, x1, y1, x2, y2, width, color):
        DrawAction.__init__(self, "Line")
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2

        self.width = width
        self.color = color

        self._hash = None

    def __hash__(self):
        if self._hash is None:
            self._hash = 0
            for member in [self.action_type, 
                           self.x1, self.y1, 
                           self.x2, self.y2, 
                           self.color, 
                           self.width]:
                self._hash = hash(self._hash + hash(member))
        return self._hash 

    def xml(self):
        "Returns an ElementTree of this object"
        root = ET.Element(self.action_type)
        x = ET.SubElement(root, "x1")
        x.text = str(self.x1)

        y = ET.SubElement(root, "y1")
        y.text = str(self.y1)

        x = ET.SubElement(root, "x2")
        x.text = str(self.x2)

        y = ET.SubElement(root, "y2")
        y.text = str(self.y2)

        color = ET.SubElement(root, "color")
        color.text = str(self.color)

        width = ET.SubElement(root, "width")
        width.text = str(self.width)

        return root

class DrawText(DrawAction):
    def __init__(self, x, y, text, size, color):
        DrawAction.__init__(self, "Text")
        self.x = x
        self.y = y
        self.text = text
        self.size = size
        self.color = color

        self._hash = None

    def __hash__(self):
        if self._hash is None:
            self._hash = 0
            for member in [self.action_type, 
                           self.x, self.y, 
                           self.text,
                           self.size,
                           self.color]:
                self._hash = hash(self._hash + hash(member))
        return self._hash 

    def xml(self):
        "Returns an ElementTree of this object"
        root = ET.Element(self.action_type)
        x = ET.SubElement(root, "x")
        x.text = str(self.x)

        y = ET.SubElement(root, "y")
        y.text = str(self.y)

        text_el = ET.SubElement(root, "text")
        text_el.text = str(self.text)

        color = ET.SubElement(root, "color")
        color.text = str(self.color)

        size = ET.SubElement(root, "size")
        size.text = str(self.size)

        return root
        
class ImgProcThread (threading.Thread):
    "A Thread that continually pulls image data from imgQ and puts the resulting stroke list in strokeQ"
    def __init__(self, imgQ, strokeQ):
        threading.Thread.__init__(self)
        self.daemon = True

        self.img_queue = imgQ
        self.stk_queue = strokeQ
    def run(self):
        while True:
            image = StringIO.StringIO(self.img_queue.get())
            logger.debug("Processing net image")
            stks = imageBufferToStrokes(image)
            logger.debug("Processed net image, converting strokes")
            newStrokeList = []
            for stk in stks:
                newStroke = Stroke()
                for x,y in stk.points:
                   scale = WIDTH / GETNORMWIDTH()
                   newPoint = Point(scale * x, HEIGHT - scale * y)
                   newStroke.addPoint(newPoint)
                newStrokeList.append(newStroke)
            self.stk_queue.put(newStrokeList)
    

class NetSketchGUI(_SketchGUI):

    Singleton = None
    def __init__(self):
       "Set up members for this GUI"
       NetSketchGUI.Singleton = self

       #Board related init
       self._Board = None
       self.ResetBoard()

       # Private data members
       self._strokeQueue = Queue.Queue()
       self._serverThread = None
       self._xmlResponseQueue = None
       self._imgProcThread = None
       self._setupImageServer()

       self._drawQueue = []

       self._onBoard = set([])
       self._onBoardDrawOrder = []

       self.run()

    def ResetBoard(self):
        "Clear all strokes and board observers from the board (logically and visually)"
        self._Board = BoardSingleton(reset = True)
        CircleObserver.CircleMarker()
        #CircleObserver.CircleVisualizer()
        ArrowObserver.ArrowMarker()
        #ArrowObserver.ArrowVisualizer()
        #LineObserver.LineMarker()
        #LineObserver.LineVisualizer()
        TextObserver.TextCollector()
        #TextObserver.TextVisualizer()
        DiGraphObserver.DiGraphMarker()
        #DiGraphObserver.DiGraphVisualizer()
        #DiGraphObserver.DiGraphExporter()
        TuringMachineObserver.TuringMachineCollector()
        #TuringMachineObserver.TuringMachineVisualizer()
        #TuringMachineObserver.TuringMachineExporter()
        
        #TemplateObserver.TemplateMarker()
        #TemplateObserver.TemplateVisualizer()
        
        
        d = DebugObserver.DebugObserver()
        #d.trackAnnotation(TestAnimObserver.TestAnnotation)
        #d.trackAnnotation(MSAxesObserver.LabelMenuAnnotation)
        #d.trackAnnotation(MSAxesObserver.LegendAnnotation)
        #d.trackAnnotation(LineObserver.LineAnnotation)
        #d.trackAnnotation(ArrowObserver.ArrowAnnotation)
        #d.trackAnnotation(MSAxesObserver.AxesAnnotation)
        #d.trackAnnotation(TemplateObserver.TemplateAnnotation)
        #d.trackAnnotation(CircleObserver.CircleAnnotation)
        #d.trackAnnotation(RaceTrackObserver.RaceTrackAnnotation)
        #d.trackAnnotation(RaceTrackObserver.SplitStrokeAnnotation)
        
        #d.trackAnnotation(TuringMachineObserver.TuringMachineAnnotation)
        #d.trackAnnotation(DiGraphObserver.DiGraphAnnotation)
        #d.trackAnnotation(TextObserver.TextAnnotation)
        #d.trackAnnotation(BarAnnotation)
        


    def _setupImageServer(self):
        "Set up the server thread to start listening for image data, which it puts into its response queue. Then the imgprocthread converts image data to strokes, which are enqueued in self._strokeQueue"
        self._serverThread = ServerThread(port = 30000)
        img_recv_queue = self._serverThread.getRequestQueue()
        self._xmlResponseQueue = self._serverThread.getResponseQueue()

        self._imgProcThread = ImgProcThread(img_recv_queue, self._strokeQueue)
        self._imgProcThread.start()

        self._serverThread.start()

    def drawCircle(self, x, y, radius=1, color="#000000", fill="", width=1.0):
        "Draw a circle on the canvas at (x,y) with radius rad. Color should be 24 bit RGB string #RRGGBB. Empty string is transparent"
        drawAction = DrawCircle(x,y,radius, color, fill, width)
        self._drawQueue.append(drawAction)
    def drawLine(self, x1, y1, x2, y2, width=2, color="#000000"):
        "Draw a line on the canvas from (x1,y1) to (x2,y2). Color should be 24 bit RGB string #RRGGBB"
        drawAction = DrawLine(x1,y1,x2,y2, width, color)
        self._drawQueue.append(drawAction)

    def drawText (self, x, y, InText="", size=10, color="#000000"):
        "Draw some text (InText) on the canvas at (x,y). Color as defined by 24 bit RGB string #RRGGBB"
        drawAction = DrawText(x,y,InText,size,color)
        self._drawQueue.append(drawAction)

    def drawStroke(self, stroke, width = 2, color="#000000", erasable = False):
        logger.debug("Drawing stroke")
        drawAction = DrawStroke(stroke, width, color)       
        self._drawQueue.append(drawAction)


    def _serializeAnnotations(self):
        "Add raw annotations to the draw queue so that they are sent with the strokes"
        for anno in self._Board.FindAnnotations():
            self._drawQueue.append(anno)

    def run(self):
        while True:
            logger.debug("Waiting on queue")
            try:
                
                self.ResetBoard()
                strokeList = self._strokeQueue.get(True, 300000)
                for stk in strokeList:
                    self._Board.AddStroke(stk)
                self._strokeQueue.task_done()

                for stk in self._Board.Strokes:
                    stk.drawMyself()

                self._serializeAnnotations()
                    
                for obs in self._Board.GetBoardObservers():
                    obs.drawMyself()

                self._processDrawQueue()
            except Queue.Empty as e:
                logger.debug("No strokes yet...")
    def _processDrawQueue(self):
        "Go through the draw queue and draw what needs to be drawn"
        drawXML = ET.Element("Board")
        drawXML.attrib['height'] = str(HEIGHT)
        drawXML.attrib['width'] = str(WIDTH)
        count = 0
        for action in self._drawQueue:
            drawXML.append(action.xml())
            count+= 1

        fp = open("xmlout.xml", "w")
        print >> fp, ET.tostring(drawXML)
        fp.close()

        self._xmlResponseQueue.put(ET.tostring(drawXML))
        logger.debug("Drawing\n%s" % (ET.tostring(drawXML)[:5000]))
        logger.debug("Done drawing")
        self._drawQueue = []

            

def SketchGUISingleton():
    if NetSketchGUI.Singleton == None:
        NetSketchGUI()
    return NetSketchGUI.Singleton

def run():
    NetSketchGUI.Singleton = NetSketchGUI()
