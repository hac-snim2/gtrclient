from common import GtR, Paging, MIME_MAP
import urler

class GtRCerif(GtR):
    def __init__(self, base_url, page_size=25, serialisation="json", username=None, password=None):
        super(GtRCerif, self).__init__(base_url, page_size, serialisation, username, password)
        
        self.factory = CerifDAOFactory()
        
        self.project_base = self.base_url + "/cerif/cfproj/"
        self.orgunit_base = self.base_url + "/cerif/cforgunit/"
        self.person_base = self.base_url + "/cerif/cfpers/"
        self.class_scheme_base = self.base_url + "/cerif/cfclassscheme/"
        self.class_base = self.base_url + "/cerif/cfclass"
        self.fund_base = self.base_url + "/cerif/cffund/"
        self.meas_base = self.base_url + "/cerif/cfmeas/"
        self.paddr_base = self.base_url + "/cerif/cfpaddr/"
        self.patent_base = self.base_url + "/cerif/cfrespat/"
        self.product_base = self.base_url + "/cerif/cfresprod/"
        self.publications_base = self.base_url + "/cerif/cfrespubl/"
        
        self.class_cache = None
        
    def project(self, uuid):
        url = self.project_base + uuid
        raw, _ = self._api(url)
        if raw is not None:
            return Project(self, raw)
        return None
        
    def cerif_class(self, uuid):
        # load the class cache if necessary
        if self.class_cache is None:
            classes, _ = self._api(self.class_base)
            cs = [c.get("cfClass") for c in classes.get("cfClassOrCfClassSchemeOrCfClassSchemeDescr", [])]
            self.class_cache = {}
            for c in cs:
                self.class_cache[c.get("cfClassId")] = c
            
        # check the cache
        if uuid in self.class_cache:
            return CerifClass(self, self.class_cache[uuid])
        return None

class CerifDAOFactory(object):
    def __init__(self):
        self.class_map = {
            "application/xml" : {
            #    "projects" : ProjectsXMLDAO,
            #    "organisations" : OrganisationsXMLDAO,
            #    "people" : PeopleXMLDAO,
            #    "publications" : PublicationsXMLDAO,
                "project" : ProjectXMLDAO #,
            #    "organisation" : OrganisationXMLDAO,
            #    "person" : PersonXMLDAO,
            #    "publication" : PublicationXMLDAO
            },
            "application/json" : {
            #    "projects" : ProjectsJSONDAO,
            #    "organisations" : OrganisationsJSONDAO,
            #    "people" : PeopleJSONDAO,
            #    "publications" : PublicationsJSONDAO,
                "project" : ProjectJSONDAO,
            #    "organisation" : OrganisationJSONDAO,
            #    "person" : PersonJSONDAO,
            #    "publication" : PublicationJSONDAO,
                "cerif_relation" : CerifRelationJSONDAO,
                "cerif_class" : CerifClassJSONDAO,
            }
        }
    
    def projects(self, client, data):
        return self._load(client, data, "projects")
        
    def project(self, client, data):
        return self._load(client, data, "project")
        
    def organisations(self, client, data):
        return self._load(client, data, "organisations")
    
    def organisation(self, client, data):
        return self._load(client, data, "organisation")
    
    def people(self, client, data):
        return self._load(client, data, "people")
    
    def person(self, client, data):
        return self._load(client, data, "person")
    
    def publications(self, client, data):
        return self._load(client, data, "publications")
    
    def publication(self, client, data):
        return self._load(client, data, "publication")
        
    def cerif_relation(self, client, data):
        return self._load(client, data, "cerif_relation")
        
    def cerif_class(self, client, data):
        return self._load(client, data, "cerif_class")
    
    def _load(self, client, data, domain):
        klazz = self.class_map.get(client.mimetype, {}).get(domain)
        if domain is not None:
            return klazz(data)
        return None

class Project(object):
    def __init__(self, client, raw, dao=None):
        # super(Project, self).__init__(client)
        self.client = client
        self.dao = dao if dao is not None else client.factory.project(client, raw)
        
    def org_cerif_relations(self):
        return self.dao.cerif_relations(self.client, name="{urn:xmlns:org:eurocris:cerif-1.5-1}cfProj_OrgUnit")
        

class ProjectXMLDAO(object):
    def __init__(self, raw):
        self.raw = raw
        
class ProjectJSONDAO(object):
    def __init__(self, raw):
        self.raw = raw
    
    def cerif_relations(self, client, name=None):
        if name is None:
            return None
        
        root = self.raw.get("cfClassOrCfClassSchemeOrCfClassSchemeDescr", [])
        
        if len(root) == 0:
            return None
        
        proj = root[0].get("cfProj", {})
        
        return [CerifRelation(client, data.get("JAXBElement", {})) 
                    for data in proj.get("cfTitleOrCfAbstrOrCfKeyw", []) 
                    if data.get("JAXBElement", {}).get("name") == name]

class CerifRelation(object):
    def __init__(self, client, raw, dao=None):
        self.client = client
        self.dao = dao if dao is not None else client.factory.cerif_relation(client, raw)
        
    def class_scheme_id(self):
        return self.dao.class_scheme_id()
        
    def class_id(self):
        return self.dao.class_id()
        
    def value(self):
        return self.dao.value()

class CerifRelationJSONDAO(object):
    def __init__(self, raw):
        self.raw = raw
        
    def as_dict(self):
        return self.raw
        
    def class_scheme_id(self):
        return self.raw.get("value", {}).get("cfClassSchemeId")
        
    def class_id(self):
        return self.raw.get("value", {}).get("cfClassId")
        
    def value(self):
        return self.raw.get("value", {}).get("value")

class CerifClass(object):
    def __init__(self, client, raw, dao=None):
        self.client = client
        self.dao = dao if dao is not None else client.factory.cerif_class(client, raw)
        
    def term_cerif_relations(self):
        return self.dao.cerif_relations(self.client, name="{urn:xmlns:org:eurocris:cerif-1.5-1}cfTerm")
    
class CerifClassJSONDAO(object):
    def __init__(self, raw):
        self.raw = raw
        
    def as_dict(self):
        return self.raw

    def cerif_relations(self, client, name=None):
        if name is None:
            return None
        
        return [CerifRelation(client, data.get("JAXBElement", {})) 
                    for data in self.raw.get("cfDescrOrCfDescrSrcOrCfTerm", []) 
                    if data.get("JAXBElement", {}).get("name") == name]

    
    


