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
import os, os.path, sys, traceback, unicodedata, shutil

# ------------------------------------------------------------------------------
class FolderDeleter:
    def delete(dirName):
        '''Recursively deletes p_dirName.'''
        dirName = os.path.abspath(dirName)
        for root, dirs, files in os.walk(dirName, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        os.rmdir(dirName)
    delete = staticmethod(delete)

# ------------------------------------------------------------------------------
extsToClean = ('.pyc', '.pyo')
def cleanFolder(folder, exts=extsToClean, verbose=False):
    '''This function allows to remove, in p_folder and subfolders, any file
       whose extension is in p_exts.'''
    if verbose: print 'Cleaning folder', folder, '...'
    # Remove files with an extension listed in exts
    for root, dirs, files in os.walk(folder):
        for fileName in files:
            ext = os.path.splitext(fileName)[1]
            if (ext in exts) or ext.endswith('~'):
                fileToRemove = os.path.join(root, fileName)
                if verbose: print 'Removing %s...' % fileToRemove
                os.remove(fileToRemove)

# ------------------------------------------------------------------------------
def copyFolder(source, dest, cleanDest=False):
    '''Copies the content of folder p_source to folder p_dest. p_dest is
       created, with intermediary subfolders if required. If p_cleanDest is
       True, it removes completely p_dest if it existed.'''
    dest = os.path.abspath(dest)
    # Delete the dest folder if required
    if os.path.exists(dest) and cleanDest:
        FolderDeleter.delete(dest)
    # Create the dest folder if it does not exist
    if not os.path.exists(dest):
        os.makedirs(dest)
    # Copy the content of p_source to p_dest.
    for name in os.listdir(source):
        sourceName = os.path.join(source, name)
        destName = os.path.join(dest, name)
        if os.path.isfile(sourceName):
            # Copy a single file
            shutil.copy(sourceName, destName)
        elif os.path.isdir(sourceName):
            # Copy a subfolder (recursively)
            copyFolder(sourceName, destName)

# ------------------------------------------------------------------------------
def encodeData(data, encoding=None):
    '''Applies some p_encoding to string p_data, but only if an p_encoding is
       specified.'''
    if not encoding: return data
    return data.encode(encoding)

# ------------------------------------------------------------------------------
def copyData(data, target, targetMethod, type='string', encoding=None,
             chunkSize=1024):
    '''Copies p_data to a p_target, using p_targetMethod. For example, it copies
       p_data which is a string containing the binary content of a file, to
       p_target, which can be a HTTP connection or a file object.

       p_targetMethod can be "write" (files) or "send" (HTTP connections) or ...
       p_type can be "string", "file" or "zope". In the latter case it is an
       instance of OFS.Image.File. If p_type is "file", one may, in p_chunkSize,
       specify the amount of bytes transmitted at a time.

       If an p_encoding is specified, it is applied on p_data before copying.

       Note that if the p_target is a Python file, it must be opened in a way
       that is compatible with the content of p_data, ie file('myFile.doc','wb')
       if content is binary.'''
    dump = getattr(target, targetMethod)
    if type == 'string': dump(encodeData(data, encoding))
    elif type == 'file':
        while True:
            chunk = data.read(chunkSize)
            if not chunk: break
            dump(encodeData(chunk, encoding))
    elif type == 'zope':
        # A OFS.Image.File instance can be split into several chunks
        if isinstance(data.data, basestring): # One chunk
            dump(encodeData(data.data, encoding))
        else:
            # Several chunks
            data = data.data
            while data is not None:
                dump(encodeData(data.data, encoding))
                data = data.next

# ------------------------------------------------------------------------------
class Traceback:
    '''Dumps the last traceback into a string.'''
    def get():
        res = ''
        excType, excValue, tb = sys.exc_info()
        tbLines = traceback.format_tb(tb)
        for tbLine in tbLines:
            res += ' %s' % tbLine
        res += ' %s: %s' % (str(excType), str(excValue))
        return res
    get = staticmethod(get)

# ------------------------------------------------------------------------------
def getOsTempFolder():
    tmp = '/tmp'
    if os.path.exists(tmp) and os.path.isdir(tmp):
        res = tmp
    elif os.environ.has_key('TMP'):
        res = os.environ['TMP']
    elif os.environ.has_key('TEMP'):
        res = os.environ['TEMP']
    else:
        raise "Sorry, I can't find a temp folder on your machine."
    return res

# ------------------------------------------------------------------------------
def executeCommand(cmd):
    '''Executes command p_cmd and returns the content of its stderr.'''
    childStdIn, childStdOut, childStdErr = os.popen3(cmd)
    res = childStdErr.read()
    childStdIn.close(); childStdOut.close(); childStdErr.close()
    return res

# ------------------------------------------------------------------------------
unwantedChars = ('\\', '/', ':', '*', '?', '"', '<', '>', '|', ' ')
def normalizeString(s, usage='fileName'):
    '''Returns a version of string p_s whose special chars have been
       replaced with normal chars.'''
    # We work in unicode. Convert p_s to unicode if not unicode.
    if isinstance(s, str):           s = s.decode('utf-8')
    elif not isinstance(s, unicode): s = unicode(s)
    if usage == 'fileName':
        # Remove any char that can't be found within a file name under
        # Windows or that could lead to problems with OpenOffice.
        res = ''
        for char in s:
            if char not in unwantedChars:
                res += char
        s = res
    return unicodedata.normalize('NFKD', s).encode("ascii","ignore")

# ------------------------------------------------------------------------------
typeLetters = {'b': bool, 'i': int, 'j': long, 'f':float, 's':str, 'u':unicode,
               'l': list, 'd': dict}

# ------------------------------------------------------------------------------
class CodeAnalysis:
    '''This class holds information about some code analysis (line counts) that
       spans some folder hierarchy.'''
    def __init__(self, name):
        self.name = name # Let's give a name for the analysis
        self.numberOfFiles = 0 # The total number of analysed files
        self.emptyLines = 0 # The number of empty lines within those files
        self.commentLines = 0 # The number of comment lines
        # A code line is defined as anything that is not an empty or comment
        # line.
        self.codeLines = 0

    def numberOfLines(self):
        '''Computes the total number of lines within analysed files.'''
        return self.emptyLines + self.commentLines + self.codeLines

    def analyseZptFile(self, theFile):
        '''Analyses the ZPT file named p_fileName.'''
        inDoc = False
        for line in theFile:
            stripped = line.strip()
            # Manage a comment
            if not inDoc and (line.find('<tal:comment ') != -1):
                inDoc = True
            if inDoc:
                self.commentLines += 1
                if line.find('</tal:comment>') != -1:
                    inDoc = False
                continue
            # Manage an empty line
            if not stripped:
                self.emptyLines += 1
            else:
                self.codeLines += 1

    docSeps = ('"""', "'''")
    def isPythonDoc(self, line, start, isStart=False):
        '''Returns True if we find, in p_line, the start of a docstring (if
           p_start is True) or the end of a docstring (if p_start is False).
           p_isStart indicates if p_line is the start of the docstring.'''
        if start:
            res = line.startswith(self.docSeps[0]) or \
                  line.startswith(self.docSeps[1])
        else:
            sepOnly = (line == self.docSeps[0]) or (line == self.docSeps[1])
            if sepOnly:
                # If the line contains the separator only, is this the start or
                # the end of the docstring?
                if isStart: res = False
                else: res = True
            else:
                res = line.endswith(self.docSeps[0]) or \
                      line.endswith(self.docSeps[1])
        return res

    def analysePythonFile(self, theFile):
        '''Analyses the Python file named p_fileName.'''
        # Are we in a docstring ?
        inDoc = False
        for line in theFile:
            stripped = line.strip()
            # Manage a line that is within a docstring
            inDocStart = False
            if not inDoc and self.isPythonDoc(stripped, start=True):
                inDoc = True
                inDocStart = True
            if inDoc:
                self.commentLines += 1
                if self.isPythonDoc(stripped, start=False, isStart=inDocStart):
                    inDoc = False
                continue
            # Manage an empty line
            if not stripped:
                self.emptyLines += 1
                continue
            # Manage a comment line
            if line.startswith('#'):
                self.commentLines += 1
                continue
            # If we are here, we have a code line.
            self.codeLines += 1

    def analyseFile(self, fileName):
        '''Analyses file named p_fileName.'''
        self.numberOfFiles += 1
        theFile = file(fileName)
        if fileName.endswith('.py'):
            self.analysePythonFile(theFile)
        elif fileName.endswith('.pt'):
            self.analyseZptFile(theFile)
        theFile.close()

    def printReport(self):
        '''Returns the analysis report as a string, only if there is at least
           one analysed line.'''
        lines = self.numberOfLines()
        if not lines: return
        commentRate = (self.commentLines / float(lines)) * 100.0
        blankRate = (self.emptyLines / float(lines)) * 100.0
        print '%s: %d files, %d lines (%.0f%% comments, %.0f%% blank)' % \
              (self.name, self.numberOfFiles, lines, commentRate, blankRate)

# ------------------------------------------------------------------------------
class LinesCounter:
    '''Counts and classifies the lines of code within a folder hierarchy.'''
    def __init__(self, folderOrModule):
        if isinstance(folderOrModule, basestring):
            # It is the path of some folder
            self.folder = folderOrModule
        else:
            # It is a Python module
            self.folder = os.path.dirname(folderOrModule.__file__)
        # These dicts will hold information about analysed files
        self.python = {False: CodeAnalysis('Python'),
                       True:  CodeAnalysis('Python (test)')}
        self.zpt = {False: CodeAnalysis('ZPT'),
                    True:  CodeAnalysis('ZPT (test)')}
        # Are we currently analysing real or test code?
        self.inTest = False

    def printReport(self):
        '''Displays on stdout a small analysis report about self.folder.'''
        for zone in (False, True): self.python[zone].printReport()
        for zone in (False, True): self.zpt[zone].printReport()

    def run(self):
        '''Let's start the analysis of self.folder.'''
        # The test markers will allow us to know if we are analysing test code
        # or real code within a given part of self.folder code hierarchy.
        testMarker1 = '%stest%s' % (os.sep, os.sep)
        testMarker2 = '%stest' % os.sep
        j = os.path.join
        for root, folders, files in os.walk(self.folder):
            rootName = os.path.basename(root)
            if rootName.startswith('.') or \
               (rootName in ('tmp', 'temp')):
                continue
            # Are we in real code or in test code ?
            self.inTest = False
            if root.endswith(testMarker2) or (root.find(testMarker1) != -1):
                self.inTest = True
            # Scan the files in this folder
            for fileName in files:
                if fileName.endswith('.py'):
                    self.python[self.inTest].analyseFile(j(root, fileName))
                elif fileName.endswith('.pt'):
                    self.zpt[self.inTest].analyseFile(j(root, fileName))
        self.printReport()
# ------------------------------------------------------------------------------
