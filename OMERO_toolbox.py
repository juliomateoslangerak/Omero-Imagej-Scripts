from java.lang import String
from java.lang import Long
from java.lang import Float
from java.lang import Double
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
from omero.gateway.facility import TablesFacility

from omero.gateway.model import ProjectData
from omero.gateway.model import DatasetData
from omero.gateway.model import ImageData
from omero.gateway.model import ExperimenterData
from omero.gateway.model import AnnotationData
from omero.gateway.model import MapAnnotationData
from omero.gateway.model import TagAnnotationData
from omero.gateway.model import TableDataColumn
from omero.gateway.model import TableData
from omero.log import Logger
from omero.log import SimpleLogger
from omero.model import ProjectI
from omero.model import DatasetI
from omero.model import ImageI
from omero.model import Pixels
from omero.model import TagAnnotationI
from omero.model import NamedValue
from omero.model import ProjectAnnotationLinkI
from omero.model import DatasetAnnotationLinkI
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

TYPES_DICT = {'String':String,
              'Long':Long,
              'Float':Float,
              'Double':Double}

def open_image_plus(host, username, password, group_id, image_id):

    options = ""
    options += "location=[OMERO] open=[omero:server="
    options += host
    options += "\nuser="
    options += username
    options += "\npass="
    options += password
    options += "\ngroupID="
    options += String.valueOf(group_id)
    options += "\niid="
    options += String.valueOf(image_id)
    options += "]"
    options += " windowless=true "

    IJ.runPlugIn("loci.plugins.LociImporter", options)


def omero_connect(host, port, user_name, user_password):
    """Omero Connect with credentials and simple_logger"""

    cred = LoginCredentials()
    cred.getServer().setHostname(host)
    cred.getServer().setPort(port)
    cred.getUser().setUsername(user_name.strip())
    cred.getUser().setPassword(user_password.strip())
    simple_logger = SimpleLogger()
    gateway = Gateway(simple_logger)
    gateway.connect(cred)
    return gateway


def _get_images_browser(gateway, dataset_id):
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

    browser = _get_images_browser(gateway, dataset_id)
    image_ids = [String.valueOf(image.getId()) for image in browser]
    return image_ids


def get_image_properties(gateway, dataset_id):
    """Returns a dictionary of dictionaries in the form:
    {long:{'name': str,
           'acquisition_date': ,
           'description': str,
           'fileset_id': ,
           'index': ,
           'instrument_id': ,
           'file_path': str,}
    under the specified Dataset
    """

    browser = _get_images_browser(gateway, dataset_id)
    image_properties = {}
    for image in browser:
        image_id = image.getId()
        properties = {'name': image.getName(),
                      'acquisition_date': image.getAcquisitionDate(),
                      'description': image.getDescription(),
                      'fileset_id': image.getFilesetId(),
                      'index': image.getIndex(),
                      'instrument_id': image.getInstrumentId(),
                      'file_path': image.getPathToFile(),
                      }
        image_properties[image_id] = properties
    return image_properties


def upload_image(gateway, path, host, dataset_id):

    user = gateway.getLoggedInUser()
    ctx = SecurityContext(user.getGroupId())
    session_key = gateway.getSessionId(user)
    
    str2d = Array.newInstance(String,[1])
    str2d[0] = path
    
    config = ImportConfig()

    config.email.set("")
    config.sendFiles.set('true')
    config.sendReport.set('false')
    config.contOnError.set('false')
    config.debug.set('false')
    config.hostname.set(host)
    config.sessionKey.set(session_key)
    config.targetClass.set("omero.model.Dataset")
    config.targetId.set(dataset_id)

    loci.common.DebugTools.enableLogging("DEBUG")

    store = config.createStore()
    reader = OMEROWrapper(config)

    library = ImportLibrary(store,reader)
    error_handler = ErrorHandler(config)

    library.addObserver(LoggingImportMonitor())
    candidates = ImportCandidates(reader, str2d, error_handler)
    reader.setMetadataOptions(DefaultMetadataOptions(MetadataLevel.ALL))
    print('Importing image: ' + str2d[0])
    success = library.importCandidates(config, candidates)
    return success


def _data_manager_generator(gateway):
    data_manager = gateway.getFacility(DataManagerFacility)
    user = gateway.getLoggedInUser()
    ctx = SecurityContext(user.getGroupId())

    return data_manager, ctx


def _dict_to_map_annotation(dictionary, description=None):
    result = []
    for element in dictionary:
        result.append(NamedValue(element, dictionary[element]))
    map_data = MapAnnotationData()
    map_data.setContent(result)
    if description:
        map_data.setDescription(description)
    map_data.setNameSpace(MapAnnotationData.NS_CLIENT_CREATED)

    return map_data


def add_projects_key_values(gateway, key_values, project_ids, description=None):
    """Adds some key:value pairs to a list of images"""
    map_data = _dict_to_map_annotation(key_values, description)

    data_manager, ctx = _data_manager_generator(gateway)

    # Link the data to the image
    if not hasattr(project_ids, '__iter__'):
        project_ids = [project_ids]
    for ID in project_ids:
        link = ProjectAnnotationLinkI()
        link.setChild(map_data.asAnnotation())
        link.setParent(ProjectI(ID, False))
        data_manager.saveAndReturnObject(ctx, link)


def add_datasets_key_values(gateway, key_values, dataset_ids, description=None):
    """Adds some key:value pairs to a list of images"""
    map_data = _dict_to_map_annotation(key_values, description)

    data_manager, ctx = _data_manager_generator(gateway)

    # Link the data to the image
    if not hasattr(dataset_ids, '__iter__'):
        dataset_ids = [dataset_ids]
    for ID in dataset_ids:
        link = DatasetAnnotationLinkI()
        link.setChild(map_data.asAnnotation())
        link.setParent(DatasetI(ID, False))
        data_manager.saveAndReturnObject(ctx, link)


def add_images_key_values(gateway, key_values, image_ids, description=None):
    """Adds some key:value pairs to a list of images"""
    map_data = _dict_to_map_annotation(key_values, description)

    data_manager, ctx = _data_manager_generator(gateway)

    # Link the data to the image
    if not hasattr(image_ids, '__iter__'):
        image_ids = [image_ids]
    for ID in image_ids:
        link = ImageAnnotationLinkI()
        link.setChild(map_data.asAnnotation())
        link.setParent(ImageI(ID, False))
        data_manager.saveAndReturnObject(ctx, link)


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


def _add_table(gateway, table_parameters, table_data, table_name, target):
    """Appends a table to a target object"""
    # Verify consistency of tables
    if len(table_parameters) != len(table_data):
        raise Exception('Table parameters and data do not have the same length')

    columns = []
    for i in range(len(table_parameters)):
        columns.append(TableDataColumn(table_parameters[i][0],
                                       i,
                                       table_parameters[i][1]))
        if len(table_parameters[i]) == 3:
            columns[-1].setDescription(table_parameters[i][2])

    table = TableData(columns, table_data)

    facility = gateway.getFacility(TablesFacility)
    user = gateway.getLoggedInUser()
    ctx = SecurityContext(user.getGroupId())

    facility.addTable(ctx, target, table_name, table)


def add_project_table(gateway, table_parameters, table_data, table_name, project_ids):
    """Appends a table to a project.

    :param gateway: a gateway to the omero server
    :param table_parameters: a list of 2 or 3 element-tuples containing:
        1- a string with column name
        2- a string with data type. Allowed values are: 'String', 'Long', 'Double'
        3- optional, a string containing the description of the column
    :param table_data: a list of lists containing the data
    :param table_name: a string containing the table name. Must be unique
    :param project_ids: the id (of list of ids) of the target project(s)
    """
    if not hasattr(project_ids, '__iter__'):
        project_ids = [project_ids]
    for project in project_ids:
        target = ProjectI(project, False)
        try:
            _add_table(gateway, table_parameters, table_data, table_name, target)
        except Exception as e:
            print(e)


def add_dataset_table(gateway, table_parameters, table_data, table_name, dataset_ids):
    """Appends a table to a project.

    :param gateway: a gateway to the omero server
    :param table_parameters: a list of 2 or 3 element-tuples containing:
        1- a string with column name
        2- a string with data type. Allowed values are: 'String', 'Long', 'Double'
        3- optional, a string containing the description of the column
    :param table_data: a list of lists containing the data
    :param table_name: a string containing the table name. Must be unique
    :param dataset_ids: the id (of list of ids) of the target dataset(s)
    """
    if not hasattr(dataset_ids, '__iter__'):
        dataset_ids = [dataset_ids]
    for dataset in dataset_ids:
        target = DatasetI(dataset, False)
        try:
            _add_table(gateway, table_parameters, table_data, table_name, target)
        except Exception as e:
            print(e)


def add_image_table(gateway, table_parameters, table_data, table_name, image_ids):
    """Appends a table to a project.

    :param gateway: a gateway to the omero server
    :param table_parameters: a list of 2 or 3 element-tuples containing:
        1- a string with column name
        2- a string with data type. Allowed values are: 'String', 'Long', 'Double'
        3- optional, a string containing the description of the column
    :param table_data: a list of lists containing the data
    :param table_name: a string containing the table name. Must be unique
    :param image_ids: the id (of list of ids) of the target image(s)
    """
    if not hasattr(image_ids, '__iter__'):
        image_ids = [image_ids]
    for image in image_ids:
        target = ImageI(image, False)
        try:
            _add_table(gateway, table_parameters, table_data, table_name, target)
        except Exception as e:
            print(e)


def _get_available_tables(gateway, target):
    facility = gateway.getFacility(TablesFacility)
    user = gateway.getLoggedInUser()
    ctx = SecurityContext(user.getGroupId())

    return facility.getAvailableTables(ctx, target)


def get_project_tables_file_names(gateway, project_id):
    """Returns a list with all the table names available in the project"""
    target = ProjectI(project_id, False)
    tables = _get_available_tables(gateway, target)

    return [t.getFileName() for t in tables]


def get_dataset_tables_file_names(gateway, dataset_id):
    """Returns a list with all the table names available in the project"""
    target = DatasetI(dataset_id, False)
    tables = _get_available_tables(gateway, target)

    return [t.getFileName() for t in tables]


def get_image_tables_file_names(gateway, image_id):
    """Returns a list with all the table names available in the project"""
    target = ImageI(image_id, False)
    tables = _get_available_tables(gateway, target)

    return [t.getFileName() for t in tables]



