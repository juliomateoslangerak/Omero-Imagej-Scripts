from java.lang import Long
from java.lang import String
from java.lang.Long import longValue
from java.util import ArrayList
from jarray import array
from java.lang.reflect import Array
import java

# Preparations
# Drop omero_client.jar and Blitz.jar under the jars folder of FIJI

# Omero Dependencies
from omero.gateway import Gateway
from omero.gateway import LoginCredentials
from omero.gateway import SecurityContext
from omero.gateway.exception import DSAccessException
from omero.gateway.exception import DSOutOfServiceException
from omero.gateway.facility import BrowseFacility
from omero.gateway.facility import DataManagerFacility

from omero.gateway.model import ProjectData
from omero.gateway.model import DatasetData
from omero.gateway.model import ImageData
from omero.gateway.model import ExperimenterData
from omero.gateway.model import AnnotationData
from omero.gateway.model import MapAnnotationData
from omero.gateway.model import TagAnnotationData
from omero.log import Logger
from omero.log import SimpleLogger
from omero.model import ProjectI
from omero.model import DatasetI
from omero.model import ImageI
from omero.model import Pixels
from omero.model import TagAnnotationI
from omero.model import NamedValue
from omero.model import ProjectAnnotationLinkI
from omero.model import ImageAnnotationLinkI

from ome.formats.importer import ImportConfig
from ome.formats.importer import OMEROWrapper
from ome.formats.importer import ImportLibrary
from ome.formats.importer import ImportCandidates
from ome.formats.importer.cli import ErrorHandler
from ome.formats.importer.cli import LoggingImportMonitor
import loci.common
from loci.formats.in import DefaultMetadataOptions
from loci.formats.in import MetadataLevel
from ij import IJ

def open_image_plus(HOST,USERNAME,PASSWORD,groupId,imageId):

    options = ""
    options += "location=[OMERO] open=[omero:server="
    options += HOST
    options += "\nuser="
    options += USERNAME
    options += "\npass="
    options += PASSWORD
    options += "\ngroupID="
    options += String.valueOf(groupId)
    options += "\niid="
    options += String.valueOf(imageId)
    options += "]"
    options += " windowless=true "

    IJ.runPlugIn("loci.plugins.LociImporter", options);


def omero_connect(host, port, user_name, user_password):
    """Omero Connect with credentials and simpleLogger"""

    cred = LoginCredentials()
    cred.getServer().setHostname(host)
    cred.getServer().setPort(port)
    cred.getUser().setUsername(user_name.strip())
    cred.getUser().setPassword(user_password.strip())
    simpleLogger = SimpleLogger()
    gateway = Gateway(simpleLogger)
    gateway.connect(cred)
    return gateway


def _get_browse_facility(gateway, dataset_id):
    browse = gateway.getFacility(BrowseFacility)
    user = gateway.getLoggedInUser()
    ctx = SecurityContext(user.getGroupId())
    ids = ArrayList(1)
    val = Long(dataset_id)
    ids.add(val)
    images = browse.getImagesForDatasets(ctx, ids)
    return images.iterator()


def get_image_ids(gateway, dataset_id):
    """Returns a list of all ImageId's under a Project/Dataset"""

    browser = _get_browse_facility(gateway, dataset_id)
    image_ids = [String.valueOf(image.getId()) for image in browser]
    return image_ids


def get_image_name_id_dict(gateway, dataset_id):
    """Returns a dictionary with image Name: image ID under a Project/Dataset"""

    browser = _get_browse_facility(gateway, dataset_id)
    image_name_id = {}
    for image in browser:
        image_name_id[String.valueOf(image.getName())] = image.getId()
    return image_name_id


def upload_image(gateway, path, host, dataset_id):

    user = gateway.getLoggedInUser()
    ctx = SecurityContext(user.getGroupId())
    sessionKey = gateway.getSessionId(user)

    config = ImportConfig()

    config.email.set("")
    config.sendFiles.set('true')
    config.sendReport.set('false')
    config.contOnError.set('false')
    config.debug.set('false')
    config.hostname.set(host)
    config.sessionKey.set(sessionKey)
    config.targetClass.set("omero.model.Dataset")
    config.targetId.set(dataset_id)

    loci.common.DebugTools.enableLogging("DEBUG")

    store = config.createStore()
    reader = OMEROWrapper(config)

    library = ImportLibrary(store,reader)
    errorHandler = ErrorHandler(config)

    library.addObserver(LoggingImportMonitor())
    candidates = ImportCandidates (reader, path, errorHandler)
    reader.setMetadataOptions(DefaultMetadataOptions(MetadataLevel.ALL))
    success = library.importCandidates(config, candidates)
    return success


def add_images_key_values(gateway, key_values, image_ids, description=None):
    """Adds some key:value pairs to a list of images"""
    data_manager = gateway.getFacility(DataManagerFacility)
    user = gateway.getLoggedInUser()
    ctx = SecurityContext(user.getGroupId())

    # Arrange the data
    result = []
    for element in key_values:
        result.append(NamedValue(element, key_values[element]))
    map_data = MapAnnotationData()
    map_data.setContent(result)
    if description:
        map_data.setDescription(description)
    map_data.setNameSpace(MapAnnotationData.NS_CLIENT_CREATED)

    # Link the data to the image
    if not hasattr(image_ids, '__iter__'):
        image_ids = [image_ids]
    for image_id in image_ids:
        link = ImageAnnotationLinkI()
        link.setChild(map_data.asAnnotation())
        link.setParent(ImageI(image_id, False))

        return data_manager.saveAndReturnObject(ctx, link)


def add_project_tag(gateway, tag_text, project_id, description=None):
    """Adds a tag to a project"""
    data_manager = gateway.getFacility(DataManagerFacility)
    user = gateway.getLoggedInUser()
    ctx = SecurityContext(user.getGroupId())

    # Arrange the data
    tag_data = TagAnnotationData(tag_text)
    if description:
        tag_data.setTagDescription(description)

    # Link the data to the image
    link = ProjectAnnotationLinkI()
    link.setChild(tag_data.asAnnotation())
    link.setParent(ProjectI(project_id, False))

    return data_manager.saveAndReturnObject(ctx, link)


def add_dataset_tag(gateway, tag_text, dataset_id, description=None):
    """Adds a tag to a dataset"""
    data_manager = gateway.getFacility(DataManagerFacility)
    user = gateway.getLoggedInUser()
    ctx = SecurityContext(user.getGroupId())

    # Arrange the data
    tag_data = TagAnnotationData(tag_text)
    if description:
        tag_data.setTagDescription(description)

    # Link the data to the image
    link = DatasetAnnotationLinkI()
    link.setChild(tag_data.asAnnotation())
    link.setParent(DatasetI(dataset_id, False))

    return data_manager.saveAndReturnObject(ctx, link)


def add_image_tag(gateway, tag_text, image_id, description=None):
    """Adds a tag to an image"""
    data_manager = gateway.getFacility(DataManagerFacility)
    user = gateway.getLoggedInUser()
    ctx = SecurityContext(user.getGroupId())

    # Arrange the data
    tag_data = TagAnnotationData(tag_text)
    if description:
        tag_data.setTagDescription(description)

    # Link the data to the image
    link = ImageAnnotationLinkI()
    link.setChild(tag_data.asAnnotation())
    link.setParent(ImageI(image_id, False))

    return data_manager.saveAndReturnObject(ctx, link)
