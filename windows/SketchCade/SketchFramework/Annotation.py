import datetime

#--------------------------------------------
class Annotation(object):
    "Base Annotation Class, it is a container for data placed on sets of strokes."

    def __init__(self):
        self.Strokes = [] # list of strokes that this annotates
        self.Time = datetime.datetime.utcnow() # time used for debuging replay

    def isType( self, arg):
        "Input: either a classobj, or a list of classobjs.  Return true if this class is one of the classobjs listed"
        if type(arg) is list:
            clist = arg
        else:
            clist = [arg]
        if self.__class__ in clist:
            return True
        else:
            return False

    def classname( self ):
        "Returns a string with the name of this type of annotation"
        return self.__class__.__name__ 

#--------------------------------------------
class AnnotatableObject(object):
    "The fundamental Board Object that can be annotated with information and drawn on the board"
    Name = "Annotatable Object"
    def __init__(self, center=None, drawMe = False):
        self.DrawMe = drawMe

        self.Annotations = {}
        # FIXME: remove parents
        self.Parents = []
        self.X = self.Y = -1
        self.Center = center
        if center != None:
            self.X = self.Center.X
            self.Y = self.Center.Y

    def findAnnotations( self, annoType=None, searchParents=False ):    
        "Input: Type annotation, bool searchParent.  Returns a list of the annotations of the specified type found on this object and it's parents if option is chosen"
        annoList = []
        if annoType == None:
            foundAnno = []
            for annos in self.Annotations.values():
                foundAnno.extend(annos)
        else:
            foundAnno = self.Annotations.get(annoType)
        if foundAnno != None:
            annoList.extend( foundAnno )
        self._gatherAnnotations( annoList, self.Parents, annoType )
        return annoList
       
    def _gatherAnnotations( self, annoList, ParentList, annoType ):
        "Recursively searches parents for an Annotation type and adds them to Annotation List"
        for obj in ParentList:
            if annoType == None:
                foundAnno = obj.Annotations
            else:
                foundAnno = obj.Annotations.Get(annoType)
            if foundAnno != None:
                annoList.extend( foundAnno )
            _GatherAnnotations( annoList, obj.Parents, annoType )   #TODO:  Handle cyclical stuff.
            #see if parent has the anno.  if so, add to annoList, then  search the parent's parents
