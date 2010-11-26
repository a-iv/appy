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
import re

from appy.pod import PodError, XML_SPECIAL_CHARS
from appy.pod.elements import *
from appy.pod.actions import IfAction, ElseAction, ForAction, VariableAction, \
                             NullAction
from appy.shared import xmlPrologue

# ------------------------------------------------------------------------------
class ParsingError(Exception): pass

# ParsingError-related constants -----------------------------------------------
ELEMENT = 'identifies the part of the document that will be impacted ' \
          'by the command. It must be one of %s.' % str(PodElement.POD_ELEMS)
FOR_EXPRESSION = 'must be of the form: {name} in {expression}. {name} must be '\
                 'a Python variable name. It is the name of the iteration ' \
                 'variable. {expression} is a Python expression that, when ' \
                 'evaluated, produces a Python sequence (tuple, string, list, '\
                 'etc).'
POD_STATEMENT = 'A Pod statement has the ' \
                'form: do {element} [{command} {expression}]. {element} ' + \
                ELEMENT + ' Optional {command} can be "if" ' \
                '(conditional inclusion of the element) or "for" (multiple ' \
                'inclusion of the element). For an "if" command, {expression} '\
                'is any Python expression. For a "for" command, {expression} '+\
                FOR_EXPRESSION
FROM_CLAUSE = 'A "from" clause has the form: from {expression}, where ' \
              '{expression} is a Python expression that, when evaluated, ' \
              'produces a valid chunk of odt content that will be inserted ' \
              'instead of the element that is the target of the note.'
BAD_STATEMENT_GROUP = 'Syntax error while parsing a note whose content is ' \
                      '"%s". In a note, you may specify at most 2 lines: a ' \
                      'pod statement and a "from" clause. ' + POD_STATEMENT + \
                      ' ' + FROM_CLAUSE
BAD_STATEMENT = 'Syntax error for statement "%s". ' + POD_STATEMENT
BAD_ELEMENT = 'Bad element "%s". An element ' + ELEMENT
BAD_MINUS = "The '-' operator can't be used with element '%s'. It can only be "\
            "specified for elements among %s."
ELEMENT_NOT_FOUND = 'Action specified element "%s" but available elements ' \
                    'in this part of the document are %s.'
BAD_FROM_CLAUSE = 'Syntax error in "from" clause "%s". ' + FROM_CLAUSE
DUPLICATE_NAMED_IF = 'An "if" statement with the same name already exists.'
ELSE_WITHOUT_IF = 'No previous "if" statement could be found for this "else" ' \
                  'statement.'
ELSE_WITHOUT_NAMED_IF = 'I could not find an "if" statement named "%s".'
BAD_FOR_EXPRESSION = 'Bad "for" expression "%s". A "for" expression ' + \
                     FOR_EXPRESSION
BAD_VAR_EXPRESSION = 'Bad variable definition "%s". A variable definition ' \
    'must have the form {name} = {expression}. {name} must be a Python-' \
    'compliant variable name. {expression} is a Python expression. When ' \
    'encountering such a statement, pod will define, in the specified part ' \
    'of the document, a variable {name} whose value will be the evaluated ' \
    '{expression}.'
EVAL_EXPR_ERROR = 'Error while evaluating expression "%s". %s'
NULL_ACTION_ERROR = 'There was a problem with this action. Possible causes: ' \
                    '(1) you specified no action (ie "do text") while not ' \
                    'specifying any from clause; (2) you specified the from ' \
                    'clause on the same line as the action, which is not ' \
                    'allowed (ie "do text from ...").'
# ------------------------------------------------------------------------------
class BufferIterator:
    def __init__(self, buffer):
        self.buffer = buffer
        self.remainingSubBufferIndexes = self.buffer.subBuffers.keys()
        self.remainingElemIndexes = self.buffer.elements.keys()
        self.remainingSubBufferIndexes.sort()
        self.remainingElemIndexes.sort()
    def hasNext(self):
        return self.remainingSubBufferIndexes or self.remainingElemIndexes
    def next(self):
        nextSubBufferIndex = None
        if self.remainingSubBufferIndexes:
            nextSubBufferIndex = self.remainingSubBufferIndexes[0]
        nextExprIndex = None
        if self.remainingElemIndexes:
            nextExprIndex = self.remainingElemIndexes[0]
        # Compute min between nextSubBufferIndex and nextExprIndex
        if (nextSubBufferIndex != None) and (nextExprIndex != None):
            res = min(nextSubBufferIndex, nextExprIndex)
        elif (nextSubBufferIndex == None) and (nextExprIndex != None):
            res = nextExprIndex
        elif (nextSubBufferIndex != None) and (nextExprIndex == None):
            res = nextSubBufferIndex
        # Update "remaining" lists
        if res == nextSubBufferIndex:
            self.remainingSubBufferIndexes = self.remainingSubBufferIndexes[1:]
            resDict = self.buffer.subBuffers
        elif res == nextExprIndex:
            self.remainingElemIndexes = self.remainingElemIndexes[1:]
            resDict = self.buffer.elements
        return res, resDict[res]

# ------------------------------------------------------------------------------
class Buffer:
    '''Abstract class representing any buffer used during rendering.'''
    elementRex = re.compile('([\w-]+:[\w-]+)\s*(.*?)>', re.S)
    def __init__(self, env, parent):
        self.parent = parent
        self.subBuffers = {} # ~{i_bufferIndex: Buffer}~
        self.env = env
    def addSubBuffer(self, subBuffer=None):
        if not subBuffer:
            subBuffer = MemoryBuffer(self.env, self)
        self.subBuffers[self.getLength()] = subBuffer
        subBuffer.parent = self
        return subBuffer
    def removeLastSubBuffer(self):
        subBufferIndexes = self.subBuffers.keys()
        subBufferIndexes.sort()
        lastIndex = subBufferIndexes.pop()
        del self.subBuffers[lastIndex]
    def write(self, something): pass # To be overridden
    def getLength(self): pass # To be overridden
    def dumpStartElement(self, elem, attrs={}):
        self.write('<%s' % elem)
        for name, value in attrs.items():
            self.write(' %s="%s"' % (name, value))
        self.write('>')
    def dumpEndElement(self, elem):
        self.write('</%s>' % elem)
    def dumpElement(self, elem, content=None, attrs={}):
        '''For dumping a whole element at once.'''
        self.dumpStartElement(elem, attrs)
        if content:
            self.dumpContent(content)
        self.dumpEndElement(elem)
    def dumpContent(self, content):
        '''Dumps string p_content into the buffer.'''
        for c in content:
            if XML_SPECIAL_CHARS.has_key(c):
                self.write(XML_SPECIAL_CHARS[c])
            else:
                self.write(c)
    def dumpAttribute(self, name, value):
        self.write(''' %s="%s" ''' % (name, value))

# ------------------------------------------------------------------------------
class FileBuffer(Buffer):
    def __init__(self, env, result):
        Buffer.__init__(self, env, None)
        self.result = result
        self.content = file(result, 'w')
        self.content.write(xmlPrologue)
    def getLength(self): return 0
    # getLength is used to manage insertions into sub-buffers. But in the case
    # of a FileBuffer, we will only have 1 sub-buffer at a time, and we don't
    # care about where it will be inserted into the FileBuffer.
    def write(self, something):
        self.content.write(something.encode('utf-8'))
    def addExpression(self, expression):
        try:
            self.dumpContent(Expression(expression).evaluate(self.env.context))
        except Exception, e:
            PodError.dump(self, EVAL_EXPR_ERROR % (expression, e), dumpTb=False)
    def pushSubBuffer(self, subBuffer): pass

# ------------------------------------------------------------------------------
class MemoryBuffer(Buffer):
    actionRex = re.compile('(?:(\w+)\s*\:\s*)?do\s+(\w+)(-)?' \
                           '(?:\s+(for|if|else|with)\s*(.*))?')
    forRex = re.compile('\s*([\w\-_]+)\s+in\s+(.*)')
    varRex = re.compile('\s*([\w\-_]+)\s*=\s*(.*)')
    def __init__(self, env, parent):
        Buffer.__init__(self, env, parent)
        self.content = u''
        self.elements = {}
        self.action = None
    def addSubBuffer(self, subBuffer=None):
        sb = Buffer.addSubBuffer(self, subBuffer)
        self.content += ' ' # To avoid having several subbuffers referenced at
                            # the same place within this buffer.
        return sb
    def getFileBuffer(self):
        if isinstance(self.parent, FileBuffer):
            res = self.parent
        else:
            res = self.parent.getFileBuffer()
        return res
    def getLength(self): return len(self.content)
    def write(self, thing): self.content += thing
    def getIndex(self, podElemName):
        res = -1
        for index, podElem in self.elements.iteritems():
            if podElem.__class__.__name__.lower() == podElemName:
                if index > res:
                    res = index
        return res
    def getMainElement(self):
        res = None
        if self.elements.has_key(0):
            res = self.elements[0]
        return res
    def isMainElement(self, elem):
        res = False
        mainElem = self.getMainElement()
        if mainElem and (elem == mainElem.OD.elem):
            res = True
            # Check if this element is not found again within the buffer
            for index, podElem in self.elements.iteritems():
                if podElem.OD:
                    if (podElem.OD.elem == mainElem.OD.elem) and (index != 0):
                        res = False
                        break
        return res
    def unreferenceElement(self, elem):
        # Find last occurrence of this element
        elemIndex = -1
        for index, podElem in self.elements.iteritems():
            if podElem.OD:
                if (podElem.OD.elem == elem) and (index > elemIndex):
                    elemIndex = index
        del self.elements[elemIndex]
    def pushSubBuffer(self, subBuffer):
        '''Sets p_subBuffer at the very end of the buffer.'''
        subIndex = None
        for index, aSubBuffer in self.subBuffers.iteritems():
            if aSubBuffer == subBuffer:
                subIndex = index
                break
        if subIndex != None:
            # Indeed, it is possible that this buffer is not referenced
            # in the parent (if it is a temp buffer generated from a cut)
            del self.subBuffers[subIndex]
            self.subBuffers[self.getLength()] = subBuffer
            self.content += u' '
    def transferAllContent(self):
        '''Transfer all content to parent.'''
        if isinstance(self.parent, FileBuffer):
            # First unreference all elements
            for index in self.getElementIndexes(expressions=False):
                del self.elements[index]
            self.evaluate()
        else:
            # Transfer content in itself
            oldParentLength = self.parent.getLength()
            self.parent.write(self.content)
            # Transfer elements
            for index, podElem in self.elements.iteritems():
                self.parent.elements[oldParentLength + index] = podElem
            # Transfer subBuffers
            for index, buf in self.subBuffers.iteritems():
                self.parent.subBuffers[oldParentLength + index] = buf
        # Empty the buffer
        MemoryBuffer.__init__(self, self.env, self.parent)
        # Change buffer position wrt parent
        self.parent.pushSubBuffer(self)
    def addElement(self, elem):
        newElem = PodElement.create(elem)
        self.elements[self.getLength()] = newElem
        if isinstance(newElem, Cell) or isinstance(newElem, Table):
            newElem.tableInfo = self.env.getTable()
    def addExpression(self, expression):
        # Create the POD expression
        expr = Expression(expression)
        expr.expr = expression
        self.elements[self.getLength()] = expr
        self.content += u' ' # To be sure that an expr and an elem can't be found
                            # at the same index in the buffer.
    def createAction(self, statementGroup):
        '''Tries to create an action based on p_statementGroup. If the statement
           is not correct, r_ is -1. Else, r_ is the index of the element within
           the buffer that is the object of the action.'''
        res = -1
        try:
            # Check the whole statement group
            if not statementGroup or (len(statementGroup) > 2):
                raise ParsingError(BAD_STATEMENT_GROUP % str(statementGroup))
            # Check the statement
            statement = statementGroup[0]
            aRes = self.actionRex.match(statement)
            if not aRes:
                raise ParsingError(BAD_STATEMENT % statement)
            statementName, podElem, minus, actionType, subExpr = aRes.groups()
            if not (podElem in PodElement.POD_ELEMS):
                raise ParsingError(BAD_ELEMENT % podElem)
            if minus and (not podElem in PodElement.MINUS_ELEMS):
                raise ParsingError(
                    BAD_MINUS % (podElem, PodElement.MINUS_ELEMS))
            indexPodElem = self.getIndex(podElem)
            if indexPodElem == -1:
                raise ParsingError(
                    ELEMENT_NOT_FOUND % (podElem, str([
                        e.__class__.__name__.lower() \
                        for e in self.elements.values()])))
            podElem = self.elements[indexPodElem]
            # Check the 'from' clause
            fromClause = None
            source = 'buffer'
            if len(statementGroup) > 1:
                fromClause = statementGroup[1]
                source = 'from'
                if not fromClause.startswith('from '):
                    raise ParsingError(BAD_FROM_CLAUSE % fromClause)
                fromClause = fromClause[5:]
            # Create the action
            if actionType == 'if':
                self.action = IfAction(statementName, self, subExpr, podElem,
                                       minus, source, fromClause)
                self.env.ifActions.append(self.action)
                if self.action.name:
                    # We must register this action as a named action
                    if self.env.namedIfActions.has_key(self.action.name):
                        raise ParsingError(DUPLICATE_NAMED_IF)
                    self.env.namedIfActions[self.action.name] = self.action
            elif actionType == 'else':
                if not self.env.ifActions:
                    raise ParsingError(ELSE_WITHOUT_IF)
                # Does the "else" action reference a named "if" action?
                ifReference = subExpr.strip()
                if ifReference:
                    if not self.env.namedIfActions.has_key(ifReference):
                        raise ParsingError(ELSE_WITHOUT_NAMED_IF % ifReference)
                    linkedIfAction = self.env.namedIfActions[ifReference]
                    # This "else" action "consumes" the "if" action: this way,
                    # it is not possible to define two "else" actions related to
                    # the same "if".
                    del self.env.namedIfActions[ifReference]
                    self.env.ifActions.remove(linkedIfAction)
                else:
                    linkedIfAction = self.env.ifActions.pop()
                self.action = ElseAction(statementName, self, None, podElem,
                                         minus, source, fromClause,
                                         linkedIfAction)
            elif actionType == 'for':
                forRes = MemoryBuffer.forRex.match(subExpr.strip())
                if not forRes:
                    raise ParsingError(BAD_FOR_EXPRESSION % subExpr)
                iter, subExpr = forRes.groups()
                self.action = ForAction(statementName, self, subExpr, podElem,
                                        minus, iter, source, fromClause)
            elif actionType == 'with':
                varRes = MemoryBuffer.varRex.match(subExpr.strip())
                if not varRes:
                    raise ParsingError(BAD_VAR_EXPRESSION % subExpr)
                varName, subExpr = varRes.groups()
                self.action = VariableAction(statementName, self, subExpr,
                    podElem, minus, varName, source, fromClause)
            else: # null action
                if not fromClause:
                    raise ParsingError(NULL_ACTION_ERROR)
                self.action = NullAction(statementName, self, None, podElem,
                                         None, source, fromClause)
            res = indexPodElem
        except ParsingError, ppe:
            PodError.dump(self, ppe, removeFirstLine=True)
        return res
    def cut(self, index, keepFirstPart):
        '''Cuts this buffer into 2 parts. Depending on p_keepFirstPart, the 1st
        (from 0 to index-1) or the second (from index to the end) part of the
        buffer is returned as a MemoryBuffer instance without parent; the other
        part is self.'''
        res = MemoryBuffer(self.env, None)
        # Manage buffer meta-info (elements, expressions, subbuffers)
        iter = BufferIterator(self)
        subBuffersToDelete = []
        elementsToDelete = []
        mustShift = False
        while iter.hasNext():
            itemIndex, item = iter.next()
            if keepFirstPart:
                if itemIndex >= index:
                    newIndex = itemIndex-index
                    if isinstance(item, MemoryBuffer):
                        res.subBuffers[newIndex] = item
                        subBuffersToDelete.append(itemIndex)
                    else:
                        res.elements[newIndex] = item
                        elementsToDelete.append(itemIndex)
            else:
                if itemIndex < index:
                    if isinstance(item, MemoryBuffer):
                        res.subBuffers[itemIndex] = item
                        subBuffersToDelete.append(itemIndex)
                    else:
                        res.elements[itemIndex] = item
                        elementsToDelete.append(itemIndex)
                else:
                    mustShift = True
        if elementsToDelete:
            for elemIndex in elementsToDelete:
                del self.elements[elemIndex]
        if subBuffersToDelete:
            for subIndex in subBuffersToDelete:
                del self.subBuffers[subIndex]
        if mustShift:
            elements = {}
            for elemIndex, elem in self.elements.iteritems():
                elements[elemIndex-index] = elem
            self.elements = elements
            subBuffers = {}
            for subIndex, buf in self.subBuffers.iteritems():
                subBuffers[subIndex-index] = buf
            self.subBuffers = subBuffers
        # Manage content
        if keepFirstPart:
            res.write(self.content[index:])
            self.content = self.content[:index]
        else:
            res.write(self.content[:index])
            self.content = self.content[index:]
        return res
    def getElementIndexes(self, expressions=True):
        res = []
        for index, elem in self.elements.iteritems():
            condition = isinstance(elem, Expression)
            if not expressions:
                condition = not condition
            if condition:
                res.append(index)
        return res
    def transferActionIndependentContent(self, actionElemIndex):
        # Manage content to transfer to parent buffer
        if actionElemIndex != 0:
            actionIndependentBuffer = self.cut(actionElemIndex,
                                               keepFirstPart=False)
            actionIndependentBuffer.parent = self.parent
            actionIndependentBuffer.transferAllContent()
            self.parent.pushSubBuffer(self)
        # Manage content to transfer to a child buffer
        actionElemIndex = self.getIndex(
            self.action.elem.__class__.__name__.lower())
        # We recompute actionElemIndex because after cut it may have changed
        elemIndexes = self.getElementIndexes(expressions=False)
        elemIndexes.sort()
        if elemIndexes.index(actionElemIndex) != (len(elemIndexes)-1):
            # I must create a sub-buffer with the impactable elements after
            # the action-related element
            childBuffer = self.cut(elemIndexes[elemIndexes.index(
                actionElemIndex)+1], keepFirstPart=True)
            self.addSubBuffer(childBuffer)
            res = childBuffer
        else:
            res = self
        return res
    def getStartIndex(self, removeMainElems):
        '''When I must dump the buffer, sometimes (if p_removeMainElems is
        True), I must dump only a subset of it. This method returns the start
        index of the buffer part I must dump.'''
        if removeMainElems:
            # Find the start position of the deepest element to remove
            deepestElem = self.action.elem.DEEPEST_TO_REMOVE
            pos = self.content.find('<%s' % deepestElem.elem)
            pos = pos + len(deepestElem.elem)
            # Now we must find the position of the end of this start tag,
            # skipping potential attributes.
            inAttrValue = False # Are we parsing an attribute value ?
            endTagFound = False # Have we found the end of this tag ?
            while not endTagFound:
                pos += 1
                nextChar = self.content[pos]
                if (nextChar == '>') and not inAttrValue:
                    # Yes we have it
                    endTagFound = True
                elif nextChar == '"':
                    inAttrValue = not inAttrValue
            res = pos + 1
        else:
            res = 0
        return res
    def getStopIndex(self, removeMainElems):
        '''This method returns the stop index of the buffer part I must dump.'''
        if removeMainElems:
            ns = self.env.namespaces
            deepestElem = self.action.elem.DEEPEST_TO_REMOVE
            pos = self.content.rfind('</%s>' % deepestElem.getFullName(ns))
            res = pos
        else:
            res = self.getLength()
        return res

    reTagContent = re.compile('<(?P<p>[\w-]+):(?P<f>[\w-]+)(.*?)>.*</(?P=p):' \
                              '(?P=f)>', re.S)
    def evaluate(self, subElements=True, removeMainElems=False):
        result = self.getFileBuffer()
        if not subElements:
            # Dump the root tag in this buffer, but not its content.
            res = self.reTagContent.match(self.content.strip())
            if not res: result.write(self.content)
            else:
                g = res.group
                result.write('<%s:%s%s></%s:%s>' % (g(1),g(2),g(3),g(1),g(2)))
        else:
            iter = BufferIterator(self)
            currentIndex = self.getStartIndex(removeMainElems)
            while iter.hasNext():
                index, evalEntry = iter.next()
                result.write(self.content[currentIndex:index])
                currentIndex = index + 1
                if isinstance(evalEntry, Expression):
                    try:
                        result.dumpContent(evalEntry.evaluate(self.env.context))
                    except Exception, e:
                        PodError.dump(result, EVAL_EXPR_ERROR % (
                            evalEntry.expr, e), dumpTb=False)
                else: # It is a subBuffer
                    if evalEntry.action:
                        evalEntry.action.execute()
                    else:
                        result.write(evalEntry.content)
            stopIndex = self.getStopIndex(removeMainElems)
            if currentIndex < (stopIndex-1):
                result.write(self.content[currentIndex:stopIndex])
# ------------------------------------------------------------------------------
