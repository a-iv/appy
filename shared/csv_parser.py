# ------------------------------------------------------------------------------
# Appy is a framework for building applications in the Python language.
# Copyright (C) 2007 Gaetan Delannay

# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301,USA.

# ------------------------------------------------------------------------------
from appy.shared import UnmarshalledObject

# ------------------------------------------------------------------------------
WRONG_LINE = 'Line number %d in file %s does not have the right number of ' \
             'fields.'

class CsvParser:
    '''This class reads a CSV file and creates a list of Python objects from it.
       The first line of the CSV file must declare the format of the following
       lines, which are 'data' lines. For example, if the first line of the file
       is

       id,roles*,password

       Then subsequent lines in the CSV need to conform to this syntax. Field
       separator will be the comma. Result of method 'parse' will be a list of
       Python objects, each one having attributes id, roles and password.
       Attributes declared with a star (like 'roles') are lists. An empty value
       will produce an empty list in the resulting object; several values need
       to be separated with the '+' sign. Here are some examples of valid 'data'
       lines for the first line above:

       gdy,,
       gdy,MeetingManager,abc
       gdy,MeetingManager+MeetingMember,abc

       In the first (and subsequent) line(s), you may choose among the following
       separators: , : ; |
       '''
    separators = [',', ':', ';', '|']
    typeLetters = {'i': int, 'f': float, 's': str, 'b': bool}
    def __init__(self, fileName, references={}, klass=None):
        self.fileName = fileName
        self.res = [] # The resulting list of Python objects.
        self.sep = None
        self.attributes = None # The list of attributes corresponding to
        # CSV columns.
        self.attributesFlags = None # Here we now if every attribute is a list
        # (True) of not (False).
        self.attributesTypes = None # Here we now the type of the attribute (if
        # the attribute is a list it denotes the type of every item in the
        # list): string, integer, float, boolean.
        self.references = references
        self.klass = klass # If a klass is given here, instead of creating
        # UnmarshalledObject instances we will create instances of this class.
        # But be careful: we will not call the constructor of this class. We
        # will simply create instances of UnmarshalledObject and dynamically
        # change the class of created instances to this class.

    def identifySeparator(self, line):
        '''What is the separator used in this file?'''
        maxLength = 0
        res = None
        for sep in self.separators:
            newLength = len(line.split(sep))
            if newLength > maxLength:
                maxLength = newLength
                res = sep
        self.sep = res

    def identifyAttributes(self, line):
        self.attributes = line.split(self.sep)
        self.attributesFlags = [False] * len(self.attributes)
        self.attributesTypes = [str] * len(self.attributes)
        i = -1
        for attr in self.attributes:
            i += 1
            # Is this attribute mono- or multi-valued?
            if attr.endswith('*'):
                self.attributesFlags[i] = True
            attrNoFlag = attr.strip('*')
            attrInfo = attrNoFlag.split('-')
            # What is the type of value(s) for this attribute ?
            if (len(attrInfo) == 2) and (attrInfo[1] in self.typeLetters):
                self.attributesTypes[i] = self.typeLetters[attrInfo[1]]
        # Remove trailing stars
        self.attributes = [a.strip('*').split('-')[0] for a in self.attributes]

    def resolveReference(self, attrName, refId):
        '''Finds, in self.reference, the object having p_refId.'''
        refObjects, refAttrName = self.references[attrName]
        res = None
        for refObject in refObjects:
            if getattr(refObject, refAttrName) == refId:
                res = refObject
                break
        return res

    def convertValue(self, value, basicType):
        '''Converts the atomic p_value which is a string into some other atomic
           Python type specified in p_basicType (int, float, ...).'''
        if (basicType != str) and (basicType != unicode):
            try:
                exec 'res = %s' % str(value)
            except SyntaxError, se:
                res = None
        else:   
            try:
                exec 'res = """%s"""' % str(value)
            except SyntaxError, se:
                try:
                    exec "res = '''%s'''" % str(value)
                except SyntaxError, se:
                    res = None
        return res

    def parse(self):
        '''Parses the CSV file named self.fileName and creates a list of
           corresponding Python objects (UnmarshalledObject instances). Among
           object fields, some may be references. If it is the case, you may
           specify in p_references a dict of referred objects. The parser will
           then replace string values of some fields (which are supposed to be
           ids of referred objects) with corresponding objects in p_references.

           How does this work? p_references must be a dictionary:
           - keys correspond to field names of the current object;
           - values are 2-tuples:
             * 1st value is the list of available referred objects;
             * 2nd value is the name of the attribute on those objects that
               stores their ID.
        '''
        # The first pass parses the file and creates the Python object
        f = file(self.fileName)
        firstLine = True
        lineNb = 0
        for line in f:
            lineNb += 1
            line = line.strip()
            if not line: continue
            if firstLine:
                # The first line declares the structure of the following 'data'
                # lines.
                self.identifySeparator(line)
                self.identifyAttributes(line)
                firstLine = False
            else:
                # Add an object corresponding to this line.
                lineObject = UnmarshalledObject()
                if self.klass:
                    lineObject.__class__ = self.klass
                i = -1
                # Do we get the right number of field values on this line ?
                attrValues = line.split(self.sep)
                if len(attrValues) != len(self.attributes):
                    raise WRONG_LINE % (lineNb, self.fileName)
                for attrValue in line.split(self.sep):
                    i += 1
                    theValue = attrValue
                    vType = self.attributesTypes[i]
                    if self.attributesFlags[i]:
                        # The attribute is multi-valued
                        if not attrValue:
                            theValue = []
                        elif '+' in theValue:
                            theValue = [self.convertValue(v, vType) \
                                        for v in attrValue.split('+')]
                        else:
                            theValue = [self.convertValue(theValue, vType)]
                    else:
                        # The attribute is mono-valued
                        theValue = self.convertValue(theValue, vType)
                    setattr(lineObject, self.attributes[i], theValue)
                self.res.append(lineObject)
        f.close()
        # The second pass resolves the p_references if any
        for attrName, refInfo in self.references.iteritems():
            if attrName in self.attributes:
                # Replace ID with real object from p_references
                for obj in self.res:
                    attrValue = getattr(obj, attrName)
                    if isinstance(attrValue, list) or \
                       isinstance(attrValue, tuple):
                        # Multiple values to resolve
                        newValue = []
                        for v in attrValue:
                            newValue.append(self.resolveReference(attrName,v))
                    else:
                        # Only one value to resolve
                        newValue = self.resolveReference(attrName, attrValue)
                    setattr(obj, attrName, newValue)
        return self.res
# ------------------------------------------------------------------------------
