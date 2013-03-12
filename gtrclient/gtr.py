import requests, json
import urler, xmltodict
from lxml import etree
from copy import deepcopy

NSMAP = {"gtr" : "http://gtr.rcuk.ac.uk/api"}
GTR_PREFIX = "gtr"
MIME_MAP = {"xml" : "application/xml", "json" : "application/json"}

class GtRNative(object):
    
    def __init__(self, base_url, page_size=25, serialisation="xml", username=None, password=None):
        self.base_url = base_url
        self.username = username
        self.password = password
        self.page_size = self._constrain_page_size(page_size)
        self.serialisation = serialisation if serialisation in ["xml", "json"] else "xml"
        self.mimetype = MIME_MAP.get(self.serialisation, "application/xml")
        self.factory = GtRDAOFactory()
        
        self.project_base = self.base_url + "/project/"
        self.org_base = self.base_url + "/organisation/"
        self.person_base = self.base_url + "/person/"
        self.publication_base = self.base_url + "/publication/"
    
    ## List Retrieval Methods ##
    
    def projects(self, page=None, page_size=None):
        page_size = self._constrain_page_size(page_size)
        data, paging = self._api(self.project_base, page, page_size)
        return Projects(self, self.project_base, data, paging)
        
    def organisations(self, page=None, page_size=None):
        page_size = self._constrain_page_size(page_size)
        data, paging = self._api(self.org_base, page, page_size)
        return Organisations(self, self.org_base, data, paging)

    def people(self, page=None, page_size=None):
        page_size = self._constrain_page_size(page_size)
        data, paging = self._api(self.person_base, page, page_size)
        return People(self, self.person_base, data, paging)
        
    def publications(self, page=None, page_size=None):
        page_size = self._constrain_page_size(page_size)
        data, paging = self._api(self.publication_base, page, page_size)
        return Publications(self, self.publication_base, data, paging)
    
    ## Individual retrieval methods ##
    
    def project(self, uuid):
        url = self.project_base + uuid
        raw, paging = self._api(url)
        return Project(self, url, raw)

    def organisation(self, uuid):
        url = self.org_base + uuid
        raw, paging = self._api(url)
        return Organisation(self, url, raw, paging)
        
    def person(self, uuid):
        url = self.person_base + uuid
        raw, paging = self._api(url)
        return Person(self, url, raw)

    def publication(self, uuid):
        url = self.publication_base + uuid
        raw, paging = self._api(url)
        return Publication(self, url, raw)
        
    ## Private utility methods ##
    
    def _api(self, rest_url, mimetype=None, page=None, page_size=None):
        accept = self.mimetype
        if mimetype is not None and mimetype in MIME_MAP.values():
            accept = mimetype
        headers = {"Accept" : accept}
        
        if page is not None:
            rest_url = urler.set_query_param(rest_url, "page", page)
        
        if page_size is not None:
            rest_url = urler.set_query_param(rest_url, "fetchSize", page_size)
        
        resp = None
        if self.username is None:
            resp = requests.get(rest_url, headers=headers)
        else:
            resp = requests.get(rest_url, headers=headers, auth=(self.username, self.password))
            
        if resp is None or resp.status_code != 200:
            return None, None # FIXME: maybe raise an exception?
        
        data = None
        if accept == "application/xml":
            data = etree.fromstring(resp.text.encode("utf-8"))
        elif accept == "application/json":
            data = json.loads(resp.text)
        
        paging = self._extract_paging(resp)
        return data, paging
    
    def _extract_paging(self, resp):
        try:
            record_count = int(resp.headers.get("link-records"))
        except (ValueError, TypeError):
            record_count = None
        try:
            pages = int(resp.headers.get("link-pages"))
        except (ValueError, TypeError):
            pages = None
        
        link_header = resp.headers.get("link")
        
        if record_count is None or pages is None or link_header is None:
            return None
        
        bits = [tuple(p.split(";")) for p in link_header.split(",")]
        fpnl = [None]*4
        for bit in bits:
            if bit[1].strip() == "rel=first":
                fpnl[0] = bit[0].strip()[1:-1]
            elif bit[1].strip() == "rel=previous":
                fpnl[1] = bit[0].strip()[1:-1]
            elif bit[1].strip() == "rel=next":
                fpnl[2] = bit[0].strip()[1:-1]
            elif bit[1].strip() == "rel=last":
                fpnl[3] = bit[0].strip()[1:-1]
        
        return Paging(record_count, pages, fpnl[0], fpnl[1], fpnl[2], fpnl[3])
    
    def _constrain_page_size(self, page_size):
        if page_size is None:
            return None
        if page_size < 25:
            return 25
        if page_size > 100:
            return 100
        return page_size

class GtRDAOFactory(object):
    def __init__(self):
        self.class_map = {
            "application/xml" : {
                "projects" : ProjectsXMLDAO,
                "project" : ProjectXMLDAO
            },
            "application/json" : {
                #"projects" : ProjectsJSONDAO,
                #"project" : ProjectJSONDAO
            }
        }
    
    def projects(self, client, data):
        return self._load(client, data, "projects")
        
    def project(self, client, data):
        return self._load(client, data, "project")
    
    def _load(self, client, data, domain):
        klazz = self.class_map.get(client.mimetype, {}).get(domain)
        if domain is not None:
            return klazz(data)
        return None

class Paging(object):
    def __init__(self, record_count, pages, first, previous, next, last):
        self.record_count = record_count
        self.pages = pages
        self.first = first
        self.previous = previous
        self.next = next
        self.last = last
        
    def current_page(self):
        # oddly, we have to work this out by looking at the previous and next pages
        # although the JSON serialisation does actually provide this as part of
        # the data, the XML serialisation does not, so this is suitably general
        if self.previous is None or self.previous == "":
            return 1
        if self.next is None or self.next == "":
            return self.pages
        
        prev_page = urler.get_query_param(self.previous, "page")
        try:
            return int(prev_page) + 1
        except (ValueError, TypeError):
            pass
        
        next_page = urler.get_query_param(self.next, "page")
        try:
            return int(next_page) - 1
        except (ValueError, TypeError):
            pass
        
        return -1
        
    def current_page_size(self):
        try:
            if self.first is not None and self.first != "":
                fetch_size = urler.get_query_param(self.first, "fetchSize")
                return int(fetch_size)
        except (ValueError, TypeError):
            pass
        return -1

class Native(object):
    def __init__(self, client, url):
        self.client = client
        self.url = url
        self.dao = None

    def xml(self, pretty_print=True):
        raise NotImplementedError()
        
    def as_dict(self):
        raise NotImplementedError()
        
    def json(self):
        raise NotImplementedError()

class NativeXMLDAO(object):

    def __init__(self, raw):
        self.raw = raw
    
    ## Methods for use by extending classes ##
    
    def _from_xpath(self, xp):
        """
        return the text from the first element found by the provided xpath
        """
        els = self.raw.xpath(xp, namespaces=NSMAP)
        if els is not None and len(els) > 0:
            return els[0].text
        return None
    
    def _get_subs(self, parent_xpath, siblings=()):
        """
        get a tuple containing the text from the first sibling xpath inside each parent xpath
        """
        tups = []
        for org in self.raw.xpath(parent_xpath, namespaces=NSMAP):
            sibs = []
            for sib in siblings:
                els = org.xpath(sib, namespaces=NSMAP)
                if els is not None and len(els) > 0:
                    val = els[0].text
                    sibs.append(val)
            tups.append(tuple(sibs))
        return tups
    
    def _do_xpath(self, xp):
        """
        just apply the xpath to the raw appropriately
        """
        return self.raw.xpath(xp, namespaces=NSMAP)
    
    def _port(self, xp, new_root):
        """
        for each result for the xpath, port (via a deep copy) the result to an element 
        named by new_root
        """
        ports = []
        for el in self.raw.xpath(xp, namespaces=NSMAP): 
            root = self._gtr_element(new_root)
            for child in el:
                root.append(deepcopy(child))
            ports.append(root)
        return ports
    
    def _wrap(self, source, wrappers, clone=True):
        """
        wrap the provided element (via a deep copy if requested) in an 
        element named by wrappers (which may be a hierarchy of elements with their namespacessa
        """
        # first create the a list of elements from the hierarchy
        hierarchy = wrappers.split("/")
        elements = []
        for wrapper in hierarchy:
            parts = wrapper.split(":")
            element = None
            if len(parts) == 1:
                element = self._element(GTR_PREFIX, parts[0])
            elif len(parts) == 2:
                element = self._element(parts[0], parts[1])
            elements.append(element)
        
        if clone:
            source = deepcopy(source)
        
        # now add the elements to eachother in reverse
        for i in range(len(elements) - 1, -1, -1):
            elements[i].append(source)
            source = elements[i]
        
        return source
    
    def _element(self, prefix, name):
        return etree.Element("{" + NSMAP.get(prefix) + "}" + name, nsmap=NSMAP)
    
    def _gtr_element(self, name):
        """
        create a new element with the GTR prefix and namespace map
        """
        return self._element(GTR_PREFIX, name)
    
    def xml(self, pretty_print=True):
        return etree.tostring(self.raw, pretty_print=pretty_print)
    
class NativeJSONDAO(object):
    def __init__(self, raw):
        self.raw = raw
    
    def as_dict(self):
        return self.raw
        
    def json(self):
        return json.dumps(self.raw, indent=2)

class NativePaged(Native):
    def __init__(self, client, url, paging):
        super(NativePaged, self).__init__(client, url)
        self.paging = paging

    def record_count(self):
        return self.paging.record_count
    
    def pages(self):
        return self.paging.pages
        
    def next_page(self):
        if self.paging.next is None or self.paging.next == "":
            return False
        raw, paging = self.client._api(self.paging.next)
        self.dao.raw = raw
        self.paging = paging
        return True
    
    def previous_page(self):
        if self.paging.previous is None or self.paging.previous == "":
            return False
        raw, paging = self.client._api(self.paging.previous)
        self.dao.raw = raw
        self.paging = paging
        return True
        
    def first_page(self):
        if self.paging.first is None or self.paging.first == "":
            return False
        xml, paging = self.client._api(self.paging.first)
        self.dao.raw = xml
        self.paging = paging
        return True
        
    def last_page(self):
        if self.paging.last is None or self.paging.last == "":
            return False
        raw, paging = self.client._api(self.paging.last)
        self.dao.raw = raw
        self.paging = paging
        return True
    
    def skip_to_page(self, page):
        if self.paging.last is None or self.paging.last == "":
            return False
        if page > self.paging.last:
            return False
        if page < 1:
            return False
        raw, paging = self.client._api(self.url, page=page)
        self.dao.raw = raw
        self.paging = paging
        return True
    
    def current_page(self):
        return self.paging.current_page()
        
    def current_page_size(self):
        return self.paging.current_page_size()
        
    def list_elements(self):
        """
        subclass should implement this to return a list of Native objects.
        It will be used to run the iterator
        """
        raise NotImplementedError("list_elements has not been implemented")
    
    def __iter__(self):
        return self.iterator()
    
    def iterator(self, reset_pages=True, stop_at_page_boundary=False):
        if reset_pages:
            self.first_page()
        def f():
            while True:
                projects = self.projects()
                for p in projects:
                    yield p
                if stop_at_page_boundary:
                    break
                if not self.next_page():
                    break
        return f()
        
    def __len__(self):
        return self.record_count()


#### List Objects ####

class Projects(NativePaged):

    def __init__(self, client, url, raw, paging, dao=None):
        super(Projects, self).__init__(client, url, paging)
        self.dao = dao if dao is not None else client.factory.projects(client, raw)

    def projects(self):
        return self.dao.projects(self.client)
        
    def list_elements(self):
        return self.projects()

class ProjectsXMLDAO(NativeXMLDAO):

    project_xpath = "/gtr:projects/gtr:project"
    
    project_wrapper = "gtr:projectOverview/gtr:projectComposition"

    def __init__(self, raw):
        super(ProjectsXMLDAO, self).__init__(raw)

    def projects(self, client):
        raws = self._do_xpath(self.project_xpath)
        return [Project(client, None, self._wrap(raw, self.project_wrapper)) for raw in raws]
        
    def list_elements(self):
        return self.projects()

class Organisations(NativePaged):

    organisation_xpath = "/gtr:organisations/gtr:organisation"
    
    organisation_wrapper = "gtr:organisationOverview"

    def __init__(self, client, url, raw, paging):
        super(Organisations, self).__init__(client, url, raw, paging)

    def organisations(self):
        raws = self._do_xpath(self.organisation_xpath)
        return [Organisation(self.client, None, self._wrap(raw, self.organisation_wrapper), None) for raw in raws]
        
    def list_elements(self):
        return self.organisations()

class People(NativePaged):

    person_xpath = "/gtr:people/gtr:person"
    
    person_wrapper = "gtr:personOverview"

    def __init__(self, client, url, raw, paging):
        super(People, self).__init__(client, url, raw, paging)

    def people(self):
        raws = self._do_xpath(self.person_xpath)
        return [Person(self.client, None, self._wrap(raw, self.person_wrapper)) for raw in raws]
        
    def list_elements(self):
        return self.people()
        
class Publications(NativePaged):

    publication_xpath = "/gtr:publications/gtr:publication"
    
    publication_wrapper = "gtr:publicationOverview"

    def __init__(self, client, url, raw, paging):
        super(Publications, self).__init__(client, url, raw, paging)

    def publications(self):
        raws = self._do_xpath(self.publication_xpath)
        return [Publication(self.client, None, self._wrap(raw, self.publication_wrapper)) for raw in raws]
        
    def list_elements(self):
        return self.publications()

##### Individual Entity Objects ####

class Project(Native):
    def __init__(self, client, url, raw, dao=None):
        super(Project, self).__init__(client, url)
        self.dao = dao if dao is not None else client.factory.project(client, raw)

    def id(self): return self.dao.id()
    def title(self): return self.dao.title()
    def start(self): return self.dao.start()
    def status(self): return self.dao.status()  
    def end(self): return self.dao.end()
    def abstract(self): return self.dao.abstract()
    def funder(self): return self.dao.funder()
    def value(self): return self.dao.value()
    def category(self): return self.dao.category()
    def reference(self): return self.dao.reference()
    
    def lead(self): return self.dao.lead(self.client)
    def orgs(self): return self.dao.orgs(self.client)
    def people(self): return self.dao.people(self.client)
    
    def collaboration_outputs(self): pass
    def intellectual_property_outputs(self): pass
    def policy_influence_outputs(self): pass
    def product_outputs(self): pass
    def research_material_outputs(self): pass
    def publications(self): pass
    
    def fetch(self):
        updated_proj = self.client.project(self.id())
        self.dao.raw = updated_proj.dao.raw

class ProjectXMLDAO(NativeXMLDAO):

    composition_base = "/gtr:projectOverview/gtr:projectComposition"
    project_base = composition_base + "/gtr:project"
    
    id_xpath = project_base + "/gtr:id"
    title_xpath = project_base + "/gtr:title"
    start_xpath = project_base + "/gtr:fund/gtr:start"
    status_xpath = project_base + "/gtr:status"
    end_xpath = project_base + "/gtr:fund/gtr:end"
    abstract_xpath = project_base + "/gtr:abstractText"
    funder_xpath = project_base + "/gtr:fund/gtr:funder/gtr:name"
    value_xpath = project_base + "/gtr:fund/gtr:valuePounds"
    category_xpath = project_base + "/gtr:grantCategory"
    reference_xpath = project_base + "/gtr:grantReference"
    
    lead_xpath = composition_base + "/gtr:leadResearchOrganisation"
    orgs_xpath = composition_base + "/gtr:organisations/gtr:organisation"
    person_xpath = composition_base + "/gtr:projectPeople/gtr:projectPerson"
    collaborator_xpath = composition_base + "/gtr:collaborations/gtr:collaborator"
    
    organisation_wrapper = "organisationOverview"
    person_wrapper = "personOverview"
    
    organisation_element = "organisation"
    person_element = "person"

    def __init__(self, raw):
        super(ProjectXMLDAO, self).__init__(raw)

    def id(self):
        return self._from_xpath(self.id_xpath)

    def title(self):
        return self._from_xpath(self.title_xpath)
    
    def start(self):
        return self._from_xpath(self.start_xpath)
    
    def status(self):
        return self._from_xpath(self.status_xpath)
    
    def end(self):
        return self._from_xpath(self.end_xpath)
    
    def abstract(self):
        return self._from_xpath(self.abstract_xpath)
    
    def funder(self):
        return self._from_xpath(self.funder_xpath)
    
    def value(self):
        return self._from_xpath(self.value_xpath)
    
    def category(self):
        return self._from_xpath(self.category_xpath)
    
    def reference(self):
        return self._from_xpath(self.reference_xpath)
    
    def lead(self, client):
        raws = self._port(self.lead_xpath, self.organisation_element)
        return [Organisation(client, None, self._wrap(raw, self.organisation_wrapper), None) for raw in raws]
        
    def orgs(self, client):
        raws = self._do_xpath(self.orgs_xpath)
        return [Organisation(client, None, self._wrap(raw, self.organisation_wrapper)) for raw in raws]
        
    def people(self, client):
        raws = self._port(self.person_xpath, self.person_element)
        return [Person(client, None, self._wrap(raw, self.person_wrapper)) for raw in raws]
    
    def collaborators(self, client):
        raws = self._port(self.collaborator_xpath, self.organisation_element)
        return [Organisation(client, None, self._wrap(raw, self.organisation_wrapper)) for raw in raws]
        
class Person(Native):

    overview_base = "/gtr:personOverview"
    person_base = overview_base + "/gtr:person"
    
    id_xpath = person_base + "/gtr:id"
    name_xpath = person_base + "/gtr:name"
    projects_xpath = overview_base + "/gtr:projectCompositions/gtr:projectComposition"
    
    project_wrapper = "projectOverview"

    def __init__(self, client, url, raw):
        super(Person, self).__init__(client, url, raw)

    def id(self):
        return self._from_xpath(self.id_xpath)
        
    def name(self):
        return self._from_xpath(self.name_xpath)
            
    def projects(self):
        raws = self._do_xpath(self.projects_xpath)
        return [Project(self.client, None, self._wrap(raw, self.project_wrapper)) for raw in raws]
        
    def fetch(self):
        updated_person = self.client.person(self.id())
        self.raw = updated_person.raw

class Organisation(NativePaged):

    overview_base = "/gtr:organisationOverview"
    
    id_xpath = overview_base + "/gtr:organisation/gtr:id"
    name_xpath = overview_base + "/gtr:organisation/gtr:name"

    def __init__(self, client, url, raw, paging):
        super(Organisation, self).__init__(client, url, raw, paging)
        
    def id(self):
        return self._from_xpath(self.id_xpath)
        
    def name(self):
        return self._from_xpath(self.name_xpath)
    
    def fetch(self):
        updated_org = self.client.organisation(self.id())
        self.raw = updated_org.raw
        self.paging = updated_org.paging

class Publication(Native):
    overview_base = "/gtr:publicationOverview"
    publication_base = overview_base + "/gtr:publication"
    
    id_xpath = publication_base + "/gtr:id"
    title_xpath = publication_base + "/gtr:title"
    
    def __init__(self, client, url, raw, paging):
        super(Publication, self).__init__(client, url, raw, paging)
    
    def id(self):
        return self._from_xpath(self.id_xpath)
        
    def title(self):
        return self._from_xpath(self.title_xpath)
    
    def fetch(self):
        updated_pub = self.client.publication(self.id())
        self.raw = updated_pub.raw
    
