#!/usr/bin/python
"""
filename: TkSketchGUI.py

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


import time
from Tkinter import *
from tkMessageBox import *

from SketchFramework.SketchGUI import _SketchGUI
from SketchFramework.Point import Point
from SketchFramework.Stroke import Stroke
from SketchFramework.Board import BoardSingleton
from SketchSystem import initialize, standAloneMain

# Constants
WIDTH = 1000
HEIGHT = 800
MID_W = WIDTH/2
MID_H = HEIGHT/2


class TkSketchGUI(_SketchGUI):

    Singleton = None
    def __init__(self):
       "Set up members for this GUI"
       global HEIGHT, WIDTH
       self.sketchFrame = None

       TkSketchGUI.Singleton = self
       self.run()
    def run(self):
       root = Tk()
       root.title("Sketchy/Scratch")
       self.sketchFrame = TkSketchFrame(master = root)
       try:
           while 1:
               root.update_idletasks()
               root.update()
       except TclError:
           pass

    def drawCircle(self, x, y, radius=1, color="#000000", fill="", width=1.0):
        "Draw a circle on the canvas at (x,y) with radius rad. Color should be 24 bit RGB string #RRGGBB. Empty string is transparent"
        self. sketchFrame.drawCircle(x,y,radius=radius, color=color, fill=fill, width=width)
    def drawLine(self, x1, y1, x2, y2, width=2, color="#000000"):
        "Draw a line on the canvas from (x1,y1) to (x2,y2). Color should be 24 bit RGB string #RRGGBB"
        self.sketchFrame.drawLine(x1, y1, x2, y2, width=width, color=color)
    def drawText (self, x, y, InText="", size=10, color="#000000"):
        "Draw some text (InText) on the canvas at (x,y). Color as defined by 24 bit RGB string #RRGGBB"
        self.sketchFrame.drawText (x, y, InText=InText, size=size, color=color)

#TODO: Wrapper for TSketchGUI because This inherits from frame and we can't just switch it to inherit from SketchGUI
class TkSketchFrame(Frame):
    """The base GUI class. 
    Class must implement drawText, drawLine and drawCircle. X-Y origin is bottom-left corner.
    Aside from these restrictions, interface options (reset board, etc) are up to the GUI programmer."""
    Singleton = None
    def __init__(self, master = None, **kargs):
        "Set up the Tkinter GUI stuff as well as the board logic"
        global HEIGHT, WIDTH

        Frame.__init__(self, master, **kargs)
        self.pack()
        #Set up the GUI stuff

        self.drawMenuOptions = {}
        
        self.BoardCanvas= Canvas(self, width=WIDTH, height = HEIGHT, bg="white", bd=2)
        self.BoardCanvas.pack(side=BOTTOM)
        self.BoardCanvas.bind("<ButtonPress-1>", self.CanvasMouseDown)
        self.BoardCanvas.bind("<B1-Motion>", self.CanvasMouseDown)          
        self.BoardCanvas.bind("<ButtonRelease-1>", self.CanvasMouseUp)      

        self.Board = None
        self.CurrentPointList = []
        self.StrokeList = []

        self.ResetBoard()
        self.MakeMenu()
        #LoadStrokes()
        self.Redraw()

      
    def MakeMenu(self):
        "Reserve places in the menu for fun actions!"
        win = self.master 
        top_menu = Menu(win)
        win.config(menu=top_menu)
        
        self.object_menu = Menu(top_menu)
        top_menu.bind("<ButtonPress-1>",(lambda e: self.RebuildObjectMenu()))
        self.RebuildObjectMenu()
        top_menu.add_cascade(label="ObjectMenu", menu=self.object_menu)

        top_menu.add_command(label="Reset Board", command = (lambda :self.ResetBoard() or self.Redraw()), underline=1 )
        #top_menu.add_command(label="Load stks.txt", command = (lambda : LoadStrokes(self.StrokeList) or self.Redraw()), underline=1 )
        #top_menu.add_command(label="Save stks.txt", command = (lambda : SaveStrokes()), underline=1 )
        top_menu.add_command(label="Undo Stroke", command = (lambda :self.RemoveLatestStroke() or self.Redraw()), underline=1 )


    def RemoveLatestStroke(self):
        #pdb.set_trace()
        if len (self.StrokeList) > 0:
            stroke = self.StrokeList.pop()
            self.Board.RemoveStroke(stroke)

    def RebuildObjectMenu(self):
        "Search the board for existing objects, and add a menu entry to manipulate it (drawAll)"
        observers = BoardSingleton().GetBoardObservers()
        draw_vars = {}
        for obs in observers:
            key = obs.__class__
            if key not in self.drawMenuOptions and hasattr(obs, "DrawAll"):
                draw_vars[key] = key.DrawAll
        
        for key, var in draw_vars.items():
            self.drawMenuOptions[key] = self.object_menu.add_command(label=key.__name__,command=(lambda class_=key: self.InvertDraw(class_)), underline = 0)

    def InvertDraw(self, class_):
        "Essentially checkbox behavior for BoardObserver.DrawAll variable"
        if hasattr(class_, "DrawAll"):
            class_.DrawAll = not class_.DrawAll
            self.Redraw()


    def ResetBoard(self):
        "Clear all strokes and board observers from the board (logically and visually)"
        self.p_x = self.p_y = None

        self.Board = BoardSingleton(reset = True)
        initialize(self.Board)
        self.CurrentPointList = []
        self.StrokeList = []

                
    def CanvasMouseDown(self, event):
        "Draw a line connecting the points of a stroke as it is being drawn"
        
        x = event.x
        y = event.y
        #self.BoardCanvas.create_oval(x,y,x,y,activewidth="1", fill="black", outline = "black")
        
        if self.p_x != None and self.p_y != None:
            p_x = self.p_x
            p_y = self.p_y
            self.BoardCanvas.create_line(p_x, p_y, x ,y, fill = "black", width=2)

        x = event.x
        y = HEIGHT - event.y
        t = time.time()
        self.CurrentPointList.append(Point(x,y,t))

        self.p_x = x
        self.p_y = HEIGHT - y

    def AddCurrentStroke(self):
        if len(self.CurrentPointList) > 0:
            stroke = Stroke( self.CurrentPointList )#, smoothing=True )
            
            self.Board.AddStroke(stroke)
            self.StrokeList.append(stroke)
            self.CurrentPointList = []
            
        
    def CanvasMouseUp(self, event):
        "Finish the stroke and add it to the board"
        #start a new stroke
        self.AddCurrentStroke()
        self.p_x = self.p_y = None
        self.Redraw()
        
    def Redraw(self):
        "Find all the strokes on the board, draw them, then iterate through every object and have it draw itself"
        global HEIGHT, WIDTH
        self.BoardCanvas.delete(ALL)
        strokes = self.Board.Strokes
        observers = self.Board.BoardObservers
        for s in strokes:
	   #print "Drawing stroke %s" % (s.id)
           s.drawMyself()
        for obs in observers:
           #print "Drawing", obj.__class__.__name__
           obs.drawMyself()
        for s in strokes:
	   #print "Drawing stroke %s" % (s.id)
           s.drawMyself()

    def drawCircle(self, x, y, radius=1, color="#000000", fill="", width=1.0):
         "Draw a circle on the canvas at (x,y) with radius rad. Color should be 24 bit RGB string #RRGGBB. Empty string is transparent"
         y = HEIGHT - y
         self.BoardCanvas.create_oval(x-radius,y-radius,x+radius,y+radius,width=width, fill=fill, outline = color)
         
    def drawLine(self, x1, y1, x2, y2, width=2, color="#000000"):
         "Draw a line on the canvas from (x1,y1) to (x2,y2). Color should be 24 bit RGB string #RRGGBB"
         y1 = HEIGHT - y1
         y2 = HEIGHT - y2
         self.BoardCanvas.create_line(x1, y1, x2 ,y2, fill=color, width = width)

    def drawText (self, x, y, InText="", size=10, color="#000000"):
        "Draw some text (InText) on the canvas at (x,y). Color as defined by 24 bit RGB string #RRGGBB"
        y = HEIGHT - y
        text_font = ("times", size, "")
        self.BoardCanvas.create_text(x,y,text = InText, fill = color, font = text_font, anchor=NW) 

def TkSketchGUISingleton():
    "Returns the GUI instance we're currently working with."
    if TkSketchGUI.Singleton == None:
       TkSketchGUI.Singleton = TkSketchGUI()
    return TkSketchGUI.Singleton
    
    



def drawCircle (x, y, radius=1, color="#000000", fill="", width=1.0):
    s = TkSketchGUISingleton().sketchFrame
    s.drawCircle(x,y,radius=radius,  color=color, fill=fill, width=width)

def drawText (x, y, InText="", size=10, color="#000000"):
    s = TkSketchGUISingleton().sketchFrame
    s.drawText(x,y,InText=InText, size = size, color=color)

def drawLine(x1, y1, x2, y2, width=2, color="#000000"):
    s = TkSketchGUISingleton().sketchFrame
    s.drawLine(x1,y1,x2,y2, width=width, color=color)
    
def drawBox(topleft, bottomright, color="#000000", width=2):
    s = TkSketchGUISingleton().sketchFrame
    s.drawLine(topleft.X, topleft.Y, bottomright.X, topleft.Y, color=color, width=width)
    s.drawLine(bottomright.X, topleft.Y, bottomright.X, bottomright.Y, color=color, width=width)
    s.drawLine(bottomright.X, bottomright.Y, topleft.X, bottomright.Y, color=color, width=width)
    s.drawLine(topleft.X, bottomright.Y, topleft.X, topleft.Y, color=color, width=width)
    
def drawStroke(stroke, width = 2, color="#000000"):
    s = TkSketchGUISingleton().sketchFrame
    prev_p = None
    for next_p in stroke.Points:
        if prev_p is not None:
            s.drawLine(prev_p.X, prev_p.Y, next_p.X, next_p.Y, width = width, color=color)
        prev_p = next_p

def run():
    TkSketchGUI.Singleton = TkSketchGUI()
    """
    root = Tk()
    root.title("Sketchy/Scratch")
    app = TkSketchGUI(master = root)
    try:
    	while 1:
	    root.update_idletasks()
	    root.update()
    except TclError:
        pass
    #root.mainloop()
    """

if __name__ == "__main__":
    import TkSketchGUI as GUI
    GUI.run()




