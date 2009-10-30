# -*- coding: utf-8 -*-
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
import xml.sax
from appy.shared.xml_parser import XmlEnvironment, XmlParser
from appy.pod.odf_parser import OdfEnvironment
from appy.pod import *

# To which ODT tag does HTML tags correspond ?
HTML_2_ODT = {'h1':'h', 'h2':'h', 'h3':'h', 'h4':'h', 'h5':'h', 'h6':'h',
    'p':'p', 'b':'span', 'i':'span', 'strong':'span', 'em': 'span',
    'sub': 'span', 'sup': 'span', 'br': 'line-break', 'div': 'span'}
DEFAULT_ODT_STYLES = {'b': 'podBold', 'strong':'podBold', 'i': 'podItalic',
                      'em': 'podItalic', 'sup': 'podSup', 'sub':'podSub',
                      'td': 'podCell', 'th': 'podHeaderCell'}
INNER_TAGS = ('b', 'strong', 'i', 'em', 'sup', 'sub', 'span', 'div')
TABLE_CELL_TAGS = ('td', 'th')
OUTER_TAGS = TABLE_CELL_TAGS + ('li',)
NOT_INSIDE_P = XHTML_HEADINGS + XHTML_LISTS + ('table',) # Those elements
# can't be rendered inside paragraphs.
NOT_INSIDE_LIST = ('table',)
IGNORABLE_TAGS = ('meta', 'title', 'style')
HTML_ENTITIES = {
        'iexcl': '¡',  'cent': '¢', 'pound': '£', 'curren': '€', 'yen': '¥',
        'brvbar': 'Š', 'sect': '§', 'uml': '¨', 'copy':'©', 'ordf':'ª',
        'laquo':'«', 'not':'¬', 'shy':'­', 'reg':'®', 'macr':'¯', 'deg':'°',
        'plusmn':'±', 'sup2':'²', 'sup3':'³', 'acute':'Ž',
        'micro':'µ', 'para':'¶', 'middot':'·', 'cedil':'ž', 'sup1':'¹',
        'ordm':'º', 'raquo':'»', 'frac14':'Œ', 'frac12':'œ', 'frac34':'Ÿ',
        'iquest':'¿', 'Agrave':'À', 'Aacute':'Á', 'Acirc':'Â', 'Atilde':'Ã',
        'Auml':'Ä', 'Aring':'Å', 'AElig':'Æ', 'Ccedil':'Ç', 'Egrave':'È',
        'Eacute':'É', 'Ecirc':'Ê', 'Euml':'Ë', 'Igrave':'Ì', 'Iacute':'Í',
        'Icirc':'Î', 'Iuml':'Ï', 'ETH':'Ð', 'Ntilde':'Ñ', 'Ograve':'Ò',
        'Oacute':'Ó', 'Ocirc':'Ó', 'Otilde':'Õ', 'Ouml':'Ö', 'times':'×',
        'Oslash':'Ø', 'Ugrave':'Ù', 'Uacute':'Ú', 'Ucirc':'Û', 'Uuml':'Ü',
        'Yacute':'Ý', 'THORN':'Þ', 'szlig':'ß', 'agrave':'à', 'aacute':'á',
        'acirc':'â', 'atilde':'ã', 'auml':'ä', 'aring':'å', 'aelig':'æ',
        'ccedil':'ç', 'egrave':'è', 'eacute':'é', 'ecirc':'ê', 'euml':'ë',
        'igrave':'ì', 'iacute':'í', 'icirc':'î', 'iuml':'ï', 'eth':'ð',
        'ntilde':'ñ', 'ograve':'ò', 'oacute':'ó', 'ocirc':'ô', 'otilde':'õ',
        'ouml':'ö', 'divide':'÷', 'oslash':'ø', 'ugrave':'ù', 'uacute':'ú',
        'ucirc':'û', 'uuml':'ü', 'yacute':'ý', 'thorn':'þ', 'yuml':'ÿ',
        'euro':'€', 'nbsp':' ', "rsquo":"'", "lsquo":"'", "ldquo":"'",
        "rdquo":"'", 'ndash': ' ', 'oelig':'oe', 'quot': "'", 'mu': 'µ'}

# ------------------------------------------------------------------------------
class Entity:
    def __init__(self, name, value):
        self.name = name
        self.value = value.decode('utf-8')
    def is_internal(self): return True

# ------------------------------------------------------------------------------
class HtmlElement:
    '''Every time an HTML element is encountered during the SAX parsing,
       an instance of this class is pushed on the stack of currently parsed
       elements.'''
    elemTypes = {'p':'para', 'li':'para','ol':'list','ul':'list'}
    odfElems = {'p':'p', 'li':'list-item', 'ol': 'list', 'ul': 'list'}
    def __init__(self, elem, attrs):
        self.elem = elem
        # Keep "class" attribute (useful for finding the corresponding ODT
        # style) in some cases. Normally, basic XmlElement class stores attrs,
        # but for a strange reason those attrs are back to None (probably for
        # performance reasons they become inaccessible after a while).
        self.classAttr = None
        if attrs.has_key('class'):
            self.classAttr = attrs['class']
        self.tagsToReopen = [] # When the HTML element corresponding to self
        # is completely dumped, if there was a problem related to tags
        # inclusion, we may need to dump start tags corresponding to
        # tags that we had to close before dumping this element. This list
        # contains HtmlElement instances.
        self.tagsToClose = [] # Before dumping the closing tag corresponding
        # to self, we may need to close other tags (ie closing a paragraph
        # before closing a cell). This list contains HtmlElement instances.
        self.elemType = self.elem
        if self.elemTypes.has_key(self.elem):
            self.elemType = self.elemTypes[self.elem]

    def getOdfTag(self, env):
        '''Gets the ODF tag that corresponds to me.'''
        return '%s:%s' % (env.textNs, self.odfElems[self.elem])

    def getConflictualElements(self, env):
        '''self was just parsed. In some cases, this element can't be dumped
           in the result because there are conflictual elements among previously
           parsed opening elements (p_currentElements). For example, if we just
           dumped a "p", we can't dump a table within the "p". Such constraints
           do not hold in XHTML code but hold in ODF code.'''
        if env.currentElements:
            parentElem = env.currentElements[-1]
            # Check elements that can't be found within a paragraph
            if (parentElem.elemType=='para') and (self.elem in NOT_INSIDE_P):
                return (parentElem,)
            if (parentElem.elem in OUTER_TAGS) and parentElem.tagsToClose and \
                (parentElem.tagsToClose[-1].elem == 'p') and \
                (self.elem in NOT_INSIDE_P):
                return (parentElem.tagsToClose[-1],)
            # Check elements that can't be found within a list
            if (parentElem.elemType=='list') and (self.elem in NOT_INSIDE_LIST):
                return (parentElem,)
        return ()

    def addInnerParagraph(self, env):
        '''Dump an inner paragraph inside self (if not already done).'''
        if not self.tagsToClose:
            # We did not do it yet
            env.dumpString('<%s:p' % env.textNs)
            if self.elem == 'li':
                itemStyle = env.getCurrentElement(isList=True).elem # ul or ol
                # Which 'li'-related style must I use?
                if self.classAttr:
                    odtStyle = env.parser.caller.findStyle(
                        self.elem, classValue=self.classAttr)
                    if odtStyle and (odtStyle.name == 'podItemKeepWithNext'):
                        itemStyle += '_kwn'
                env.dumpString(' %s:style-name="%s"' % (env.textNs,
                    env.itemStyles[itemStyle]))
            env.dumpString('>')
            self.tagsToClose.append(HtmlElement('p',{}))

    def dump(self, start, env):
        '''Dumps the start or stop (depending onp_start) tag of this HTML
           element. We must take care of potential innerTags.'''
        # Compute the tag in itself
        tag = ''
        prefix = '<'
        if not start: prefix += '/'
        # Compute tag attributes
        attrs = ''
        if start:
            if self.elemType == 'list':
                # I must specify the list style
                attrs += ' %s:style-name="%s"' % (
                    env.textNs, env.listStyles[self.elem])
                if self.elem == 'ol':
                    # I have interrupted a numbered list. I need to continue
                    # the numbering.
                    attrs += ' %s:continue-numbering="true"' % env.textNs
        tag = prefix + self.getOdfTag(env) + attrs + '>'
        # Close/open subTags if any
        for subElem in self.tagsToClose:
            subTag = subElem.dump(start, env)
            if start: tag += subTag
            else: tag = subTag + tag
        return tag

    def __repr__(self):
        return '<Html "%s">' % self.elem

# ------------------------------------------------------------------------------
class HtmlTable:
    '''Represents an HTML table, and also a sub-buffer. When parsing elements
       corresponding to an HTML table (<table>, <tr>, <td>, etc), we can't dump
       corresponding ODF elements directly into the global result buffer
       (XhtmlEnvironment.res). Indeed, when dumping an ODF table, we must
       dump columns declarations at the beginning of the table. So before
       dumping rows and cells, we must know how much columns will be present
       in the table. It means that we must first parse the first <tr> entirely
       in order to know how much columns are present in the HTML table before
       dumping the ODF table. So we use this class as a sub-buffer that will
       be constructed as we parse the HTML table; when encountering the end
       of the HTML table, we will dump the result of this sub-buffer into
       the parent buffer, which may be the global buffer or another table
       buffer.'''
    def __init__(self):
        self.res = u'' # The sub-buffer.
        self.tempRes = u'' # The temporary sub-buffer, into which we will
        # dump all table sub-elements, until we encounter the end of the first
        # row. Then, we will know how much columns are defined in the table;
        # we will dump columns declarations into self.res and dump self.tempRes
        # into self.res.
        self.firstRowParsed = False # Was the first table row completely parsed?
        self.nbOfColumns = 0

# ------------------------------------------------------------------------------
class XhtmlEnvironment(XmlEnvironment):
    itemStyles = {'ul': 'podBulletItem', 'ol': 'podNumberItem',
                  'ul_kwn': 'podBulletItemKeepWithNext',
                  'ol_kwn': 'podNumberItemKeepWithNext'}
    listStyles = {'ul': 'podBulletedList', 'ol': 'podNumberedList'}
    def __init__(self, ns):
        XmlEnvironment.__init__(self)
        self.res = u''
        self.currentContent = u''
        self.currentElements = [] # Stack of currently walked elements
        self.currentLists = [] # Stack of currently walked lists (ul or ol)
        self.currentTables = [] # Stack of currently walked tables
        self.creatingRootParagraph = False
        # Within the XHTML chunk given to this parser, there may be some
        # content that is not enclosed within any tag (at "root" level). When I
        # encounter such content, I will include it into a root paragraph with
        # default style. This content may include sub-tags of course (span,
        # div, img, a...) or may already be dumped entirely if I encounter
        # "paragraph-style" sub-tags (h1, h2, p...). self.creatingRootParagraph
        # tells me if I am still in a root paragraph. So when I encounter a
        # "root" content I know if I must reopen a new paragraph or not, for
        # example.
        self.textNs = ns[OdfEnvironment.NS_TEXT]
        self.linkNs = ns[OdfEnvironment.NS_XLINK]
        self.tableNs = ns[OdfEnvironment.NS_TABLE]
        self.ignore = False # Will be True when parsing parts of the XHTML that
        # must be ignored.

    def getCurrentElement(self, isList=False):
        '''Gets the element that is on the top of self.currentElements or
           self.currentLists.'''
        res = None
        if isList:
            elements = self.currentLists # Stack of list elements only
        else:
            elements = self.currentElements # Stack of all elements (including
            # elements also pushed on other stacks, like lists and tables).
        if elements:
            res = elements[-1]
        return res

    def anElementIsMissing(self, previousElem, currentElem):
        res = False
        if previousElem and (previousElem.elem in OUTER_TAGS) and \
           ((not currentElem) or (currentElem.elem in INNER_TAGS)):
            res = True
        return res

    def dumpRootParagraph(self, currentElem=None):
        '''Dumps content that is outside any tag (directly within the root
           "podXhtml" tag.'''
        mustStartParagraph = True
        mustEndParagraph = True
        if self.creatingRootParagraph:
            mustStartParagraph = False
        if currentElem and (currentElem not in NOT_INSIDE_P+('p',)):
            mustEndParagraph = False
        if mustStartParagraph and mustEndParagraph and \
           not self.currentContent.strip():
            # In this case I would dump an empty paragraph. So I do nothing.
            return
        if mustStartParagraph:
            self.dumpStyledElement('p', {})
            self.creatingRootParagraph = True
        self.dumpCurrentContent()
        if mustEndParagraph:
            self.dumpString('</%s:p>' % self.textNs)
            self.creatingRootParagraph = False

    def dumpCurrentContent(self):
        '''Dumps content that was temporarily stored in self.currentContent
           into the result.'''
        if self.currentContent.strip():
            # Manage missing elements
            currentElem = self.getCurrentElement()
            if self.anElementIsMissing(currentElem, None):
                currentElem.addInnerParagraph(self)
            # Dump and reinitialize the current content
            for c in self.currentContent.strip('\n'):
                # We remove leading and trailing carriage returns, but not
                # whitespace because whitespace may be part of the text to dump.
                if XML_SPECIAL_CHARS.has_key(c):
                    self.dumpString(XML_SPECIAL_CHARS[c])
                else:
                    self.dumpString(c)
            self.currentContent = u''

    def dumpStyledElement(self, elem, attrs):
        '''Dumps an element that potentially has associated style
           information.'''
        self.dumpString('<%s:%s' % (self.textNs, HTML_2_ODT[elem]))
        odtStyle = self.parser.caller.findStyle(elem, attrs)
        styleName = None
        if odtStyle:
            styleName = odtStyle.name
        elif DEFAULT_ODT_STYLES.has_key(elem):
            styleName = DEFAULT_ODT_STYLES[elem]
        if styleName:
            self.dumpString(' %s:style-name="%s"' % (self.textNs, styleName))
            if (elem in XHTML_HEADINGS) and (odtStyle.outlineLevel != None):
                self.dumpString(' %s:outline-level="%d"' % (
                    self.textNs, odtStyle.outlineLevel))
        self.dumpString('>')

    def dumpTags(self, elems, start=True):
        '''Dumps a series of start or end tags (depending on p_start) of
           HtmlElement instances in p_elems.'''
        tags = ''
        for elem in elems:
            tag = elem.dump(start, self)
            if start: tags += tag
            else: tags = tag + tags
        self.dumpString(tags)

    def dumpString(self, s):
        '''Dumps arbitrary content p_s.
           If the table stack is not empty, we must dump p_s into the buffer
           corresponding to the last parsed table. Else, we must dump p_s
           into the global buffer (self.res).'''
        if self.currentTables:
            currentTable = self.currentTables[-1]
            if (not currentTable.res) or currentTable.firstRowParsed:
                currentTable.res += s
            else:
                currentTable.tempRes += s
        else:
            self.res += s

    def getTagsToReopen(self, conflictElems):
        '''Normally, tags to reopen are equal to p_conflictElems. But we have a
           special case. Indeed, if a conflict elem has itself tagsToClose,
           the last tag to close may not be needed anymore on the tag to
           reopen, so we remove it.'''
        conflictElems[-1].tagsToClose = []
        return conflictElems

    def onElementStart(self, elem, attrs):
        previousElem = self.getCurrentElement()
        if previousElem and (previousElem.elem == 'podxhtml'):
            self.dumpRootParagraph(elem)
        else:
            self.dumpCurrentContent()
        currentElem = HtmlElement(elem, attrs)
        # Manage conflictual elements
        conflictElems = currentElem.getConflictualElements(self)
        if conflictElems:
            # We must close the conflictual elements, and once the currentElem
            # will be dumped, we will re-open the conflictual elements.
            self.dumpTags(conflictElems, start=False)
            currentElem.tagsToReopen = self.getTagsToReopen(conflictElems)
        # Manage missing elements
        if self.anElementIsMissing(previousElem, currentElem):
            previousElem.addInnerParagraph(self)
        # Add the current element on the stack of walked elements
        self.currentElements.append(currentElem)
        if elem in XHTML_LISTS:
            # Update stack of current lists
            self.currentLists.append(currentElem)
        elif elem == 'table':
            # Update stack of current tables
            self.currentTables.append(HtmlTable())
        elif elem in TABLE_CELL_TAGS:
            # If we are in the first row of a table, update columns count
            currentTable = self.currentTables[-1]
            if not currentTable.firstRowParsed:
                nbOfCols = 1
                if attrs.has_key('colspan'):
                    nbOfCols = int(attrs['colspan'])
                currentTable.nbOfColumns += nbOfCols

    def onElementEnd(self, elem):
        res = None
        if elem == 'podxhtml':
            self.dumpRootParagraph()
        else:
            self.dumpCurrentContent()
        currentElem = self.currentElements.pop()
        if elem in XHTML_LISTS:
            self.currentLists.pop()
        elif elem == 'table':
            lastTable = self.currentTables.pop()
            # Dumps the content of the last parsed table into the parent buffer
            self.dumpString(lastTable.res)
        elif elem == 'tr':
            lastTable = self.currentTables[-1]
            if not lastTable.firstRowParsed:
                lastTable.firstRowParsed = True
                # First row is parsed. I know the number of columns in the
                # table: I can dump the columns declarations.
                lastTable.res += ('<%s:table-column/>' % self.tableNs) * \
                                 lastTable.nbOfColumns
                lastTable.res += lastTable.tempRes
                lastTable.tempRes = u''
        if currentElem.tagsToClose:
            self.dumpTags(currentElem.tagsToClose, start=False)
        if currentElem.tagsToReopen:
            res = currentElem.tagsToReopen
        return res

# ------------------------------------------------------------------------------
class XhtmlParser(XmlParser):
    # Initialize entities recognized by this parser
    entities = {}
    for name, value in HTML_ENTITIES.iteritems():
        entities[name] = Entity(name, value)

    def __init__(self, *args, **kwargs):
        XmlParser.__init__(self, *args, **kwargs)
        # We override self.parser: we will use a different low-level
        # xml.sax parser because we need to be able to tackle HTML as well as
        # XML entities.
        self.parser = xml.sax.make_parser(["xml.sax.drivers2.drv_xmlproc"])
        # This parser is maybe less performant than the standard expat parser
        # coded in C, but I could not find a way to manage unknown entities
        # with the expat parser.

    def lowerizeInput(self, elem, attrs=None):
        '''Because (X)HTML is case insensitive, we may receive input p_elem and
           p_attrs in lower-, upper- or mixed-case. So here we produce lowercase
           versions that will be used throughout our parser.'''
        resElem = elem.lower()
        resAttrs = attrs
        if attrs:
            resAttrs = {}
            for attrName in attrs.keys():
                resAttrs[attrName.lower()] = attrs[attrName]
        if attrs == None:
            return resElem
        else:
            return resElem, resAttrs

    def startDocument(self):
        if hasattr(self.parser._parser, 'dtd'):
            # If the parser is the standard expat, we can't deal with XHTML
            # entities
            dtd = self.parser._parser.dtd
            # Add to the list of known entities the list of XHMLT entities.
            # dtd.gen_ents only contains the 5 XML entities by default.
            dtd.gen_ents.update(self.entities)

    def startElement(self, elem, attrs):
        elem, attrs = self.lowerizeInput(elem, attrs)
        e = XmlParser.startElement(self, elem, attrs)
        e.onElementStart(elem, attrs)
        if HTML_2_ODT.has_key(elem):
            e.dumpStyledElement(elem, attrs)
        elif elem == 'a':
            e.dumpString('<%s:a %s:type="simple"' % (e.textNs, e.linkNs))
            if attrs.has_key('href'):
                e.dumpString(' %s:href="%s"' % (e.linkNs, attrs['href']))
            e.dumpString('>')
        elif elem in XHTML_LISTS:
            prologue = ''
            if len(e.currentLists) >= 2:
                # It is a list into another list. In this case the inner list
                # must be surrounded by a list-item element.
                prologue = '<%s:list-item>' % e.textNs
            e.dumpString('%s<%s:list %s:style-name="%s">' % (
                prologue, e.textNs, e.textNs, e.listStyles[elem]))
        elif elem == 'li':
            e.dumpString('<%s:list-item>' % e.textNs)
        elif elem == 'table':
            # Here we must call "dumpString" only once
            e.dumpString('<%s:table %s:style-name="podTable">' % (e.tableNs,
                                                                  e.tableNs))
        elif elem == 'thead':
            e.dumpString('<%s:table-header-rows>' % e.tableNs)
        elif elem == 'tr':
            e.dumpString('<%s:table-row>' % e.tableNs)
        elif elem in TABLE_CELL_TAGS:
            e.dumpString('<%s:table-cell %s:style-name="%s"' % \
                (e.tableNs, e.tableNs, DEFAULT_ODT_STYLES[elem]))
            if attrs.has_key('colspan'):
                e.dumpString(' %s:number-columns-spanned="%s"' % \
                    (e.tableNs, attrs['colspan']))
            e.dumpString('>')
        elif elem in IGNORABLE_TAGS:
            e.ignore = True

    def endElement(self, elem):
        elem = self.lowerizeInput(elem)
        e = XmlParser.endElement(self, elem)
        elemsToReopen = e.onElementEnd(elem)
        if HTML_2_ODT.has_key(elem):
            # For "div" elements, we put append a carriage return.
            if elem == 'div':
                e.dumpString('<%s:line-break/>' % e.textNs)
            e.dumpString('</%s:%s>' % (e.textNs, HTML_2_ODT[elem]))
        elif elem == 'a':
            e.dumpString('</%s:a>' % e.textNs)
        elif elem in XHTML_LISTS:
            epilogue = ''
            if len(e.currentLists) >= 1:
                # We were in an inner list. So we must close the list-item tag
                # that surrounds it.
                epilogue = '</%s:list-item>' % e.textNs
            e.dumpString('</%s:list>%s' % (e.textNs, epilogue))
        elif elem == 'li':
            e.dumpString('</%s:list-item>' % e.textNs)
        elif elem == 'table':
            e.dumpString('</%s:table>' % e.tableNs)
        elif elem == 'thead':
            e.dumpString('</%s:table-header-rows>' % e.tableNs)
        elif elem == 'tr':
            e.dumpString('</%s:table-row>' % e.tableNs)
        elif elem in TABLE_CELL_TAGS:
            e.dumpString('</%s:table-cell>' % e.tableNs)
        elif elem in IGNORABLE_TAGS:
            e.ignore = False
        if elemsToReopen:
            e.dumpTags(elemsToReopen)

    def characters(self, content):
        e = XmlParser.characters(self, content)
        if not e.ignore:
            e.currentContent += content

# -------------------------------------------------------------------------------
class Xhtml2OdtConverter:
    '''Converts a chunk of XHTML into a chunk of ODT.'''
    def __init__(self, xhtmlString, encoding, stylesManager, localStylesMapping,
                 ns):
        self.xhtmlString = xhtmlString
        self.encoding = encoding # Todo: manage encoding that is not utf-8
        self.stylesManager = stylesManager
        self.odtStyles = stylesManager.styles
        self.globalStylesMapping = stylesManager.stylesMapping
        self.localStylesMapping = localStylesMapping
        self.odtChunk = None
        self.xhtmlParser = XhtmlParser(XhtmlEnvironment(ns), self)

    def run(self):
        self.xhtmlParser.parse(self.xhtmlString)
        return self.xhtmlParser.env.res

    def findStyle(self, elem, attrs=None, classValue=None):
        '''Finds the ODT style that must be applied to XHTML p_elem that has
           attrs p_attrs. In some cases, p_attrs is not given; the value of the
           "class" attribute is given instead (in p_classValue).

           Here are the places where we will search, ordered by
           priority (highest first):
           (1) local styles mapping (CSS style in "class" attr)
           (2)         "            (HTML elem)
           (3) global styles mapping (CSS style in "class" attr)
           (4)          "            (HTML elem)
           (5) ODT style that has the same name as CSS style in "class" attr
           (6) Prefefined pod-specific ODT style that has the same name as
               CSS style in "class" attr
           (7) ODT style that has the same outline level as HTML elem.'''
        res = None
        cssStyleName = None
        if attrs and attrs.has_key('class'):
            cssStyleName = attrs['class']
        if classValue:
            cssStyleName = classValue
        # (1)
        if self.localStylesMapping.has_key(cssStyleName):
            res = self.localStylesMapping[cssStyleName]
        # (2)
        elif self.localStylesMapping.has_key(elem):
            res = self.localStylesMapping[elem]
        # (3)
        elif self.globalStylesMapping.has_key(cssStyleName):
            res = self.globalStylesMapping[cssStyleName]
        # (4)
        elif self.globalStylesMapping.has_key(elem):
            res = self.globalStylesMapping[elem]
        # (5)
        elif self.odtStyles.has_key(cssStyleName):
            res = self.odtStyles[cssStyleName]
        # (6)
        elif self.stylesManager.podSpecificStyles.has_key(cssStyleName):
            res = self.stylesManager.podSpecificStyles[cssStyleName]
        # (7)
        else:
            # Try to find a style with the correct outline level
            if elem in XHTML_HEADINGS:
                # Is there a delta that must be taken into account ?
                outlineDelta = 0
                if self.localStylesMapping.has_key('h*'):
                    outlineDelta += self.localStylesMapping['h*']
                elif self.globalStylesMapping.has_key('h*'):
                    outlineDelta += self.globalStylesMapping['h*']
                outlineLevel = int(elem[1]) + outlineDelta
                # Normalize the outline level
                if outlineLevel < 1: outlineLevel = 1
                res = self.odtStyles.getParagraphStyleAtLevel(outlineLevel)
        if res:
            self.stylesManager.checkStylesAdequation(elem, res)
        return res
# ------------------------------------------------------------------------------
