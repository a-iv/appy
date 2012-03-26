# ------------------------------------------------------------------------------
import re, os, os.path

# Function for creating a Zope object ------------------------------------------
def createObject(folder, id, className, appName, wf=True):
    '''Creates, in p_folder, object with some p_id. Object will be an instance
       of p_className from application p_appName. In a very special case (the
       creation of the config object), computing workflow-related info is not
       possible at this time. This is why this function can be called with
       p_wf=False.'''
    exec 'from Products.%s.%s import %s as ZopeClass' % (appName, className,
                                                         className)
    obj = ZopeClass(id)
    folder._objects = folder._objects + \
                      ({'id':id, 'meta_type':className},)
    folder._setOb(id, obj)
    obj = folder._getOb(id) # Important. Else, obj is not really in the folder.
    obj.portal_type = className
    obj.id = id
    obj._at_uid = id
    user = obj.getUser()
    if not user.getId():
        if user.name == 'System Processes':
            userId = 'admin' # This is what happens when Zope is starting.
        else:
            userId = None # Anonymous.
    else:
        userId = user.getId()
    obj.creator = userId or 'Anonymous User'
    from DateTime import DateTime
    obj.created = DateTime()
    obj.__ac_local_roles__ = { userId: ['Owner'] } # userId can be None (anon).
    if wf: obj.notifyWorkflowCreated()
    return obj

# Classes used by edit/view templates for accessing information ----------------
class Descr:
    '''Abstract class for description classes.'''
    def get(self): return self.__dict__

class GroupDescr(Descr):
    def __init__(self, group, page, metaType):
        '''Creates the data structure manipulated in ZPTs from p_group, the
           Group instance used in the field definition.'''
        self.type = 'group'
        # All p_group attributes become self attributes.
        for name, value in group.__dict__.iteritems():
            if not name.startswith('_'):
                setattr(self, name, value)
        self.columnsWidths = [col.width for col in group.columns]
        self.columnsAligns = [col.align for col in group.columns]
        # Names of i18n labels
        labelName = self.name
        prefix = metaType
        if group.label:
            if isinstance(group.label, basestring): prefix = group.label
            else: # It is a tuple (metaType, name)
                if group.label[1]: labelName = group.label[1]
                if group.label[0]: prefix = group.label[0]
        self.labelId = '%s_group_%s' % (prefix, labelName)
        self.descrId = self.labelId + '_descr'
        self.helpId  = self.labelId + '_help'
        # The name of the page where the group lies
        self.page = page.name
        # The widgets belonging to the group that the current user may see.
        # They will be stored by m_addWidget below as a list of lists because
        # they will be rendered as a table.
        self.widgets = [[]]

    @staticmethod
    def addWidget(groupDict, newWidget):
        '''Adds p_newWidget into p_groupDict['widgets']. We try first to add
           p_newWidget into the last widget row. If it is not possible, we
           create a new row.

           This method is a static method taking p_groupDict as first param
           instead of being an instance method because at this time the object
           has already been converted to a dict (for being maniputated within
           ZPTs).'''
        # Get the last row
        widgetRow = groupDict['widgets'][-1]
        numberOfColumns = len(groupDict['columnsWidths'])
        # Computes the number of columns already filled by widgetRow
        rowColumns = 0
        for widget in widgetRow: rowColumns += widget['colspan']
        freeColumns = numberOfColumns - rowColumns
        if freeColumns >= newWidget['colspan']:
            # We can add the widget in the last row.
            widgetRow.append(newWidget)
        else:
            if freeColumns:
                # Terminate the current row by appending empty cells
                for i in range(freeColumns): widgetRow.append('')
            # Create a new row
            newRow = [newWidget]
            groupDict['widgets'].append(newRow)

class PhaseDescr(Descr):
    def __init__(self, name, states, obj):
        self.name = name
        self.states = states
        self.obj = obj
        self.phaseStatus = None
        # The list of names of pages in this phase
        self.pages = []
        # The list of hidden pages in this phase
        self.hiddenPages = []
        # The dict below stores infor about every page listed in self.pages.
        self.pagesInfo = {}
        self.totalNbOfPhases = None
        # The following attributes allows to browse, from a given page, to the
        # last page of the previous phase and to the first page of the following
        # phase if allowed by phase state.
        self.previousPhase = None
        self.nextPhase = None

    def addPage(self, appyType, obj, layoutType):
        '''Adds page-related information in the phase.'''
        # If the page is already there, we have nothing more to do.
        if (appyType.page.name in self.pages) or \
           (appyType.page.name in self.hiddenPages): return
        # Add the page only if it must be shown.
        isShowableOnView = appyType.page.isShowable(obj, 'view')
        isShowableOnEdit = appyType.page.isShowable(obj, 'edit')
        if isShowableOnView or isShowableOnEdit:
            # The page must be added.
            self.pages.append(appyType.page.name)
            # Create the dict about page information and add it in self.pageInfo
            pageInfo = {'page': appyType.page,
                        'showOnView': isShowableOnView,
                        'showOnEdit': isShowableOnEdit}
            pageInfo.update(appyType.page.getInfo(obj, layoutType))
            self.pagesInfo[appyType.page.name] = pageInfo
        else:
            self.hiddenPages.append(appyType.page.name)

    def computeStatus(self, allPhases):
        '''Compute status of whole phase based on individual status of states
           in this phase. If this phase includes no state, the concept of phase
           is simply used as a tab, and its status depends on the page currently
           shown. This method also fills fields "previousPhase" and "nextPhase"
           if relevant, based on list of p_allPhases.'''
        res = 'Current'
        if self.states:
            # Compute status base on states
            res = self.states[0]['stateStatus']
            if len(self.states) > 1:
                for state in self.states[1:]:
                    if res != state['stateStatus']:
                        res = 'Current'
                        break
        else:
            # Compute status based on current page
            page = self.obj.REQUEST.get('page', 'main')
            if page in self.pages:
                res = 'Current'
            else:
                res = 'Deselected'
            # Identify previous and next phases
            for phaseInfo in allPhases:
                if phaseInfo['name'] == self.name:
                    i = allPhases.index(phaseInfo)
                    if i > 0:
                        self.previousPhase = allPhases[i-1]
                    if i < (len(allPhases)-1):
                        self.nextPhase = allPhases[i+1]
        self.phaseStatus = res

class StateDescr(Descr):
    def __init__(self, name, stateStatus):
        self.name = name
        self.stateStatus = stateStatus.capitalize()

# ------------------------------------------------------------------------------
upperLetter = re.compile('[A-Z]')
def produceNiceMessage(msg):
    '''Transforms p_msg into a nice msg.'''
    res = ''
    if msg:
        res = msg[0].upper()
        for c in msg[1:]:
            if c == '_':
                res += ' '
            elif upperLetter.match(c):
                res += ' ' + c.lower()
            else:
                res += c
    return res

# ------------------------------------------------------------------------------
class SomeObjects:
    '''Represents a bunch of objects retrieved from a reference or a query in
       the catalog.'''
    def __init__(self, objects=None, batchSize=None, startNumber=0,
                 noSecurity=False):
        self.objects = objects or [] # The objects
        self.totalNumber = len(self.objects) # self.objects may only represent a
        # part of all available objects.
        self.batchSize = batchSize or self.totalNumber # The max length of
        # self.objects.
        self.startNumber = startNumber # The index of first object in
        # self.objects in the whole list.
        self.noSecurity = noSecurity
    def brainsToObjects(self):
        '''self.objects has been populated from brains from the catalog,
           not from True objects. This method turns them (or some of them
           depending on batchSize and startNumber) into real objects.
           If self.noSecurity is True, it gets the objects even if the logged
           user does not have the right to get them.'''
        start = self.startNumber
        brains = self.objects[start:start + self.batchSize]
        if self.noSecurity: getMethod = '_unrestrictedGetObject'
        else:               getMethod = 'getObject'
        self.objects = [getattr(b, getMethod)() for b in brains]

# ------------------------------------------------------------------------------
class Keywords:
    '''This class allows to handle keywords that a user enters and that will be
       used as basis for performing requests in a Zope ZCTextIndex.'''

    toRemove = '?-+*()'
    def __init__(self, keywords, operator='AND'):
        # Clean the p_keywords that the user has entered.
        words = keywords.strip()
        if words == '*': words = ''
        for c in self.toRemove: words = words.replace(c, ' ')
        self.keywords = words.split()
        # Store the operator to apply to the keywords (AND or OR)
        self.operator = operator

    def merge(self, other, append=False):
        '''Merges our keywords with those from p_other. If p_append is True,
           p_other keywords are appended at the end; else, keywords are appended
           at the begin.'''
        for word in other.keywords:
            if word not in self.keywords:
                if append:
                    self.keywords.append(word)
                else:
                    self.keywords.insert(0, word)

    def get(self):
        '''Returns the keywords as needed by the ZCTextIndex.'''
        if self.keywords:
            op = ' %s ' % self.operator
            return op.join(self.keywords)+'*'
        return ''

# ------------------------------------------------------------------------------
def getClassName(klass, appName=None):
    '''Generates, from appy-class p_klass, the name of the corresponding
       Zope class. For some classes, name p_appName is required: it is
       part of the class name.'''
    moduleName = klass.__module__
    if (moduleName == 'appy.gen.model') or moduleName.endswith('.wrappers'):
        # This is a model (generation time or run time)
        res = appName + klass.__name__
    elif klass.__bases__ and (klass.__bases__[-1].__module__ == 'appy.gen'):
        # This is a customized class (inherits from appy.gen.Tool, User,...)
        res = appName + klass.__bases__[-1].__name__
    else: # This is a standard class
        res = klass.__module__.replace('.', '_') + '_' + klass.__name__
    return res

# ------------------------------------------------------------------------------
def updateRolesForPermission(permission, roles, obj):
    '''Adds roles from list p_roles to the list of roles that are granted
       p_permission on p_obj.'''
    from AccessControl.Permission import Permission
    # Find existing roles that were granted p_permission on p_obj
    existingRoles = ()
    for p in obj.ac_inherited_permissions(1):
        name, value = p[:2]
        if name == permission:
            perm = Permission(name, value, obj)
            existingRoles = perm.getRoles()
    allRoles = set(existingRoles).union(roles)
    obj.manage_permission(permission, tuple(allRoles), acquire=0)
# ------------------------------------------------------------------------------
