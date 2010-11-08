# ------------------------------------------------------------------------------
import appy
import os.path

# ------------------------------------------------------------------------------
appyPath = os.path.realpath(os.path.dirname(appy.__file__))
mimeTypes = {'odt': 'application/vnd.oasis.opendocument.text',
             'doc': 'application/msword',
             'rtf': 'text/rtf',
             'pdf': 'application/pdf'
             }
mimeTypesExts = {
             'application/vnd.oasis.opendocument.text': 'odt',
             'application/msword'                     : 'doc',
             'text/rtf'                               : 'rtf',
             'application/pdf'                        : 'pdf',
             'image/png'                              : 'png',
             'image/jpeg'                             : 'jpg',
             'image/gif'                              : 'gif'
             }
xmlPrologue = '<?xml version="1.0" encoding="utf-8" ?>\n'

# ------------------------------------------------------------------------------
class UnmarshalledFile:
    '''Used for producing file objects from a marshalled Python object.'''
    def __init__(self):
        self.name = '' # The name of the file on disk
        self.mimeType = None # The MIME type of the file
        self.content = '' # The binary content of the file of a file object
        self.size = 0 # The length of the file in bytes.

class UnicodeBuffer:
    '''With StringIO class, I have tons of encoding problems. So I define a
       similar class here, that uses an internal unicode buffer.'''
    def __init__(self):
        self.buffer = []
    def write(self, s):
        if s == None: return
        if isinstance(s, unicode):
            self.buffer.append(s)
        elif isinstance(s, str):
            self.buffer.append(s.decode('utf-8'))
        else:
            self.buffer.append(unicode(s))
    def getValue(self):
        return u''.join(self.buffer)

# ------------------------------------------------------------------------------
class Dummy: pass
# ------------------------------------------------------------------------------
