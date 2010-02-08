# ------------------------------------------------------------------------------
import os, os.path, time, unicodedata
from appy.shared import mimeTypes
from appy.gen.plone25.mixins import AbstractMixin
from StringIO import StringIO
import appy.pod
from appy.pod.renderer import Renderer

# ------------------------------------------------------------------------------
class PodError(Exception): pass

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

# Error-related constants ------------------------------------------------------
POD_ERROR = 'An error occurred while generating the document. Please check ' \
            'the following things if you wanted to generate the document in ' \
            'PDF, DOC or RTF: (1) OpenOffice is started in server mode on ' \
            'the port you should have specified in the PloneMeeting ' \
            'configuration (go to Site setup-> PloneMeeting configuration); ' \
            '(2) if the Python interpreter running Zope and ' \
            'Plone is not able to discuss with OpenOffice (it does not have ' \
            '"uno" installed - check it by typing "import uno" at the Python ' \
            'prompt) please specify, in the PloneMeeting configuration, ' \
            'the path to a UNO-enabled Python interpreter (ie, the Python ' \
            'interpreter included in the OpenOffice distribution, or, if ' \
            'your server runs Ubuntu, the standard Python interpreter ' \
            'installed in /usr/bin/python). Here is the error as reported ' \
            'by the appy.pod library:\n\n %s'
DELETE_TEMP_DOC_ERROR = 'A temporary document could not be removed. %s.'

# ------------------------------------------------------------------------------
class PodTemplateMixin(AbstractMixin):
    _appy_meta_type = 'podtemplate'

    unwantedChars = ('\\', '/', ':', '*', '?', '"', '<', '>', '|', ' ')
    def _getFileName(self, obj):
        '''Returns a valid, clean fileName for the document generated from
           p_self for p_obj.'''
        res = u'%s-%s' % (obj.Title().decode('utf-8'),
                          self.Title().decode('utf-8'))
        # Remove accents
        res = unicodedata.normalize('NFKD', res).encode("ascii", "ignore")
        # Remove unwanted chars (ie, chars that are not valid in file names
        # under Windows)
        finalRes = ''
        for char in res:
            if char not in self.unwantedChars:
                finalRes += char
        return finalRes

    def generateDocument(self, obj):
        '''Generates a document from this template, for object p_obj.'''
        appySelf = self.appy()
        appName = self.getProductConfig().PROJECTNAME
        appModule = getattr(self.getProductConfig(), appName)
        # Temporary file where to generate the result
        tempFileName = '%s/%s_%f.%s' % (
            getOsTempFolder(), obj.UID(), time.time(), self.getPodFormat())
        # Define parameters to pass to the appy.pod renderer
        currentUser = self.portal_membership.getAuthenticatedMember()
        podContext = {'self': obj.appy(),
                      'user': currentUser,
                      'podTemplate': appySelf,
                      'now': self.getProductConfig().DateTime(),
                      'projectFolder': os.path.dirname(appModule.__file__)
                      }
        rendererParams = {'template': StringIO(appySelf.podTemplate.content),
                          'context': podContext,
                          'result': tempFileName }
        if appySelf.tool.unoEnabledPython:
            rendererParams['pythonWithUnoPath'] = appySelf.tool.unoEnabledPython
        if appySelf.tool.openOfficePort:
            rendererParams['ooPort'] = appySelf.tool.openOfficePort
        # Launch the renderer
        try:
            renderer = Renderer(**rendererParams)
            renderer.run()
        except appy.pod.PodError, pe:
            if not os.path.exists(tempFileName):
                # In some (most?) cases, when OO returns an error, the result is
                # nevertheless generated.
                raise PodError(POD_ERROR % str(pe))
        # Open the temp file on the filesystem
        f = file(tempFileName, 'rb')
        res = f.read()
        fileName = self._getFileName(obj)
        response = obj.REQUEST.RESPONSE
        response.setHeader('Content-Type', mimeTypes[self.getPodFormat()])
        response.setHeader('Content-Disposition', 'inline;filename="%s.%s"'\
            % (fileName, self.getPodFormat()))
        f.close()
        # Returns the doc and removes the temp file
        try:
            os.remove(tempFileName)
        except OSError, oe:
            self.getProductConfig().logger.warn(DELETE_TEMP_DOC_ERROR % str(oe))
        except IOError, ie:
            self.getProductConfig().logger.warn(DELETE_TEMP_DOC_ERROR % str(ie))
        return res
# ------------------------------------------------------------------------------
