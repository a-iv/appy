# ------------------------------------------------------------------------------
import appy.gen
from appy.gen.plone25.mixins import AbstractMixin
from appy.gen.plone25.descriptors import ArchetypesClassDescriptor

# ------------------------------------------------------------------------------
class FlavourMixin(AbstractMixin):
    _appy_meta_type = 'flavour'
    def getPortalType(self, metaTypeOrAppyType):
        '''Returns the name of the portal_type that is based on
           p_metaTypeOrAppyType in this flavour.'''
        res = metaTypeOrAppyType
        isPredefined = False
        isAppy = False
        appName = self.getProductConfig().PROJECTNAME
        if not isinstance(res, basestring):
            res = ArchetypesClassDescriptor.getClassName(res)
            isAppy = True
        if res.find('Extensions_appyWrappers') != -1:
            isPredefined = True
            elems = res.split('_')
            res = '%s%s' % (elems[1], elems[4])
        elif isAppy and issubclass(metaTypeOrAppyType, appy.gen.Tool):
            # This is the custom tool
            isPredefined = True
            res = '%sTool' % appName
        elif isAppy and issubclass(metaTypeOrAppyType, appy.gen.Flavour):
            # This is the custom Flavour
            isPredefined = True
            res = '%sFlavour' % appName
        if not isPredefined:
            if self.getNumber() != 1:
                res = '%s_%d' % (res, self.number)
        return res

    def registerPortalTypes(self):
        '''Registers, into portal_types, the portal types which are specific
           to this flavour.'''
        i = -1
        registeredFactoryTypes = self.portal_factory.getFactoryTypes().keys()
        factoryTypesToRegister = []
        appName = self.getProductConfig().PROJECTNAME
        for metaTypeName in self.allMetaTypes:
            i += 1
            portalTypeName = '%s_%d' % (metaTypeName, self.number)
            # If the portal type corresponding to the meta type is
            # registered in portal_factory (in the model:
            # use_portal_factory=True), we must also register the new
            # portal_type we are currently creating.
            if metaTypeName in registeredFactoryTypes:
                factoryTypesToRegister.append(portalTypeName)
            if not hasattr(self.portal_types, portalTypeName) and \
               hasattr(self.portal_types, metaTypeName):
                # Indeed abstract meta_types have no associated portal_type
                typeInfoName = "%s: %s (%s)" % (appName, metaTypeName,
                                                metaTypeName)
                self.portal_types.manage_addTypeInformation(
                    getattr(self.portal_types, metaTypeName).meta_type,
                    id=portalTypeName, typeinfo_name=typeInfoName)
                # Set the human readable title explicitly
                portalType = getattr(self.portal_types, portalTypeName)
                portalType.title = portalTypeName
                # Associate a workflow for this new portal type.
                pf = self.portal_workflow
                workflowChain = pf.getChainForPortalType(metaTypeName)
                pf.setChainForPortalTypes([portalTypeName],workflowChain)
                # Copy actions from the base portal type
                basePortalType = getattr(self.portal_types, metaTypeName)
                portalType._actions = tuple(basePortalType._cloneActions())
                # Copy aliases from the base portal type
                portalType.setMethodAliases(basePortalType.getMethodAliases())
        # Update the factory tool with the list of types to register
        self.portal_factory.manage_setPortalFactoryTypes(
            listOfTypeIds=factoryTypesToRegister+registeredFactoryTypes)

    def getClassFolder(self, className):
        '''Return the folder related to p_className.'''
        return getattr(self, className)

    def getAvailablePodTemplates(self, obj, phase='main'):
        '''Returns the POD templates which are available for generating a
           document from p_obj.'''
        appySelf = self._appy_getWrapper()
        fieldName = 'podTemplatesFor%s' % obj.meta_type
        res = []
        podTemplates = getattr(appySelf, fieldName, [])
        if not isinstance(podTemplates, list):
            podTemplates = [podTemplates]
        res = [r.o for r in podTemplates if r.phase==phase]
        hasParents = True
        klass = obj.__class__
        while hasParents:
            parent = klass.__bases__[-1]
            if hasattr(parent, 'wrapperClass'):
                fieldName = 'podTemplatesFor%s' % parent.meta_type
                podTemplates = getattr(appySelf, fieldName, [])
                if not isinstance(podTemplates, list):
                    podTemplates = [podTemplates]
                res += [r.o for r in podTemplates if r.phase==phase]
                klass = parent
            else:
                hasParents = False
        return res

    def getMaxShownTemplates(self, obj):
        attrName = 'podMaxShownTemplatesFor%s' % obj.meta_type
        return getattr(self, attrName)

    def getAttr(self, attrName):
        '''Gets on this flavour attribute named p_attrName. Useful because we
           can't use getattr directly in Zope Page Templates.'''
        return getattr(self, attrName, None)
# ------------------------------------------------------------------------------
