import os
import sys
import shutil
import unittest
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
import logging
import SimpleITK as sitk
import pyLAR
from distutils.spawn import find_executable
import json
import threading
import Queue
from time import sleep

#
# Low-rank Image Decomposition
#

class LowRankImageDecomposition(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "Low-rank Image Decomposition"
    self.parent.categories = ["Filtering"]
    self.parent.dependencies = []
    self.parent.contributors = ["Francois Budin (Kitware Inc.)"]
    self.parent.helpText = """
    This script computes a low-rank decomposition of an input image. It returns both
     a low-rank image and a sparse image.
    """
    self.parent.acknowledgementText = """
    This work was supported, in-part, by the NIBIB
    (R41EB015775), the NINDS (R41NS081792) and the NSF (EECS-1148870)
""" # replace with organization, grant and thanks.

#
# LowRankImageDecompositionWidget
#

class LowRankImageDecompositionWidget(ScriptedLoadableModuleWidget):
  """Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  class QMovingProgressBar(qt.QProgressBar):
    def __init__(self, size=15, interval=100):
      qt.QProgressBar.__init__(self)
      self.setRange(0, size)
      self.timer = qt.QTimer()
      self.timer.setInterval(interval)
      self.timer.connect('timeout()', self._move)
      self.setTextVisible(False)

    def start(self):
      self.setValue(0)
      self.show()
      self.timer.start()

    def _move(self):
      self.value += 1
      if self.value == self.maximum:
        self.value = 0

    def stop(self):
      self.timer.stop()
      self.value = self.maximum

    def clear(self):
      self.timer.stop()
      self.hide()
      self.value = 0


  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)
    self.logic = LowRankImageDecompositionLogic()
    # Initialize variables
    self.configFile = ""
    self.Algorithm = {"Unbiased Atlas Creation": "uab",
                      "Low Rank/Sparse Decomposition": "lr",
                      "Low Rank Atlas Creation": "nglra"}
    self.errorLog = slicer.app.errorLogModel()

    # Instantiate and connect widgets ...

    examplesCollapsibleButton = ctk.ctkCollapsibleButton()
    examplesCollapsibleButton.text = "Examples"
    examplesCollapsibleButton.collapsed = True
    self.layout.addWidget(examplesCollapsibleButton)

    # Layout within a collapsible button
    examplesFormLayout = qt.QFormLayout(examplesCollapsibleButton)

    #
    # Save example configuration file Buttons
    #
    configFilesCollapsibleButton = ctk.ctkCollapsibleButton()
    configFilesCollapsibleButton.text = "Configuration Files"
    configFilesCollapsibleButton.collapsed = True
    examplesFormLayout.addRow(configFilesCollapsibleButton)
    configFormLayout = qt.QFormLayout(configFilesCollapsibleButton)
    self.exampleUABButton = qt.QPushButton("Unbiased Atlas Creation")
    self.exampleUABButton.toolTip = "Save example configuration file to run Unbiased Atlas Creation."
    self.exampleUABButton.enabled = True
    configFormLayout.addRow(self.exampleUABButton)
    self.exampleLRButton = qt.QPushButton("Low Rank/Sparse Decomposition")
    self.exampleLRButton.toolTip = "Save example configuration file to run Low Rank/Sparse Decomposition."
    self.exampleLRButton.enabled = True
    configFormLayout.addRow(self.exampleLRButton)
    self.exampleNGLRAButton = qt.QPushButton("Low Rank Atlas Creation")
    self.exampleNGLRAButton.toolTip = "Save example configuration file to run Low Rank Atlas Creation."
    self.exampleNGLRAButton.enabled = True
    configFormLayout.addRow(self.exampleNGLRAButton)

    # Download data
    dataCollapsibleButton = ctk.ctkCollapsibleButton()
    dataCollapsibleButton.text = "Download data"
    dataCollapsibleButton.collapsed = True
    examplesFormLayout.addRow(dataCollapsibleButton)
    dataFormLayout = qt.QFormLayout(dataCollapsibleButton)
    self.bulleyeButton = qt.QPushButton("Download synthetic data (Bull's eye)")
    self.bulleyeButton.toolTip = "Download synthetic data from http://slicer.kitware.com/midas3"
    self.bulleyeButton.enabled = True
    dataFormLayout.addRow(self.bulleyeButton)
    self.t1flashButton = qt.QPushButton("Download Healthy Volunteer (T1-Flash)")
    self.t1flashButton.toolTip = "Download healthy volunteer data from http://insight-journal.org/midas/community/view/21"
    self.t1flashButton.enabled = True
    dataFormLayout.addRow(self.t1flashButton)
    self.t1mprageButton = qt.QPushButton("Download Healthy Volunteer (T1-MPRage)")
    self.t1mprageButton.toolTip = "Download healthy volunteer data from http://insight-journal.org/midas/community/view/21"
    self.t1mprageButton.enabled = True
    dataFormLayout.addRow(self.t1mprageButton)
    self.t2Button = qt.QPushButton("Download Healthy Volunteer (T2)")
    self.t2Button.toolTip = "Download healthy volunteer data from http://insight-journal.org/midas/community/view/21"
    self.t2Button.enabled = True
    dataFormLayout.addRow(self.t2Button)
    self.mraButton = qt.QPushButton("Download Healthy Volunteer (MRA)")
    self.mraButton.toolTip = "Download healthy volunteer data from http://insight-journal.org/midas/community/view/21"
    self.mraButton.enabled = True
    dataFormLayout.addRow(self.mraButton)
    self.abortDownloadButton = qt.QPushButton("Abort Download")
    self.abortDownloadButton.toolTip = "Abort Downloading data"
    self.abortDownloadButton.enabled = True
    dataFormLayout.addRow(self.abortDownloadButton)
    #
    # Parameters Area
    #
    parametersCollapsibleButton = ctk.ctkCollapsibleButton()
    parametersCollapsibleButton.text = "Parameters"
    self.layout.addWidget(parametersCollapsibleButton)

    # Layout within a collapsible button
    parametersFormLayout = qt.QFormLayout(parametersCollapsibleButton)

    #
    # parameter file selector
    #
    self.selectConfigFileButton = qt.QPushButton("Select Configuration File")
    self.selectConfigFileButton.toolTip = "Select configuration file."
    parametersFormLayout.addRow(self.selectConfigFileButton)
    self.selectedConfigFile = qt.QLabel()
    parametersFormLayout.addRow(self.selectedConfigFile)

    #
    # Volume selector
    #

    self.inputSelector = slicer.qMRMLNodeComboBox()
    self.inputSelector.nodeTypes = ["vtkMRMLScalarVolumeNode"]
    self.inputSelector.selectNodeUponCreation = True
    self.inputSelector.addEnabled = False
    self.inputSelector.removeEnabled = False
    self.inputSelector.noneEnabled = True
    self.inputSelector.showHidden = False
    self.inputSelector.showChildNodeTypes = False
    self.inputSelector.setMRMLScene( slicer.mrmlScene )
    self.inputSelector.setToolTip( "Pick an input to the algorithm. Not required." )
    parametersFormLayout.addRow("Input Volume: ", self.inputSelector)

    #
    # Select algorithm
    #
    self.selectAlgorithm = qt.QButtonGroup()
    self.selectUnbiasedAtlas = qt.QRadioButton("Unbiased Atlas Creation")
    self.selectLowRankDecomposition = qt.QRadioButton("Low Rank/Sparse Decomposition")
    self.selectLowRankAtlasCreation = qt.QRadioButton("Low Rank Atlas Creation")
    self.selectAlgorithm.addButton(self.selectUnbiasedAtlas)
    self.selectAlgorithm.addButton(self.selectLowRankDecomposition)
    self.selectAlgorithm.addButton(self.selectLowRankAtlasCreation)
    parametersFormLayout.addRow(self.selectUnbiasedAtlas)
    parametersFormLayout.addRow(self.selectLowRankDecomposition)
    parametersFormLayout.addRow(self.selectLowRankAtlasCreation)

    #
    # Apply Button
    #
    self.applyButton = qt.QPushButton("Apply")
    self.applyButton.toolTip = "Run the algorithm."
    self.applyButton.enabled = False
    parametersFormLayout.addRow(self.applyButton)

    outputCollapsibleButton = ctk.ctkCollapsibleButton()
    outputCollapsibleButton.text = "Output"
    self.layout.addWidget(outputCollapsibleButton)
    # Layout within a collapsible button
    outputFormLayout = qt.QFormLayout(outputCollapsibleButton)

    # show log
    self.log = qt.QTextEdit()
    self.log.readOnly = True

    outputFormLayout.addRow(self.log)
    self.logMessage('<p>Status: <i>Idle</i>\n')

    # Add vertical spacer
    self.layout.addStretch(1)

    #Progress bar

    self.progress_bar = self.QMovingProgressBar()
    self.progress_bar.hide()
    outputFormLayout.addRow(self.progress_bar)

    # connections
    self.applyButton.connect('clicked(bool)', self.onApplyButton)
    self.selectConfigFileButton.connect('clicked(bool)', self.onSelectFile)
    self.selectUnbiasedAtlas.connect('clicked(bool)', self.onSelect)
    self.selectLowRankDecomposition.connect('clicked(bool)', self.onSelect)
    self.selectLowRankAtlasCreation.connect('clicked(bool)', self.onSelect)

    self.mapperExampleFile = qt.QSignalMapper()
    self.BullseyeFileName = "Bullseye.json"
    self.HealthyVolunteersT1FlashFileName = "HealthyVolunteers-T1-Flash.json"
    self.HealthyVolunteersT1MPRageFileName = "HealthyVolunteers-T1-MPRage.json"
    self.HealthyVolunteersMRAFileName = "HealthyVolunteers-MRA.json"
    self.HealthyVolunteersT2FileName = "HealthyVolunteers-T2.json"
    self.mapperExampleFile.connect('mapped(const QString&)', self.onDownloadData)
    self.mapperExampleFile.setMapping(self.bulleyeButton,self.BullseyeFileName)
    self.mapperExampleFile.setMapping(self.t1flashButton,self.HealthyVolunteersT1FlashFileName)
    self.mapperExampleFile.setMapping(self.t1mprageButton,self.HealthyVolunteersT1MPRageFileName)
    self.mapperExampleFile.setMapping(self.mraButton,self.HealthyVolunteersMRAFileName)
    self.mapperExampleFile.setMapping(self.t2Button,self.HealthyVolunteersT2FileName)
    self.bulleyeButton.connect('clicked()', self.mapperExampleFile, 'map()')
    self.t1flashButton.connect('clicked()', self.mapperExampleFile, 'map()')
    self.t1mprageButton.connect('clicked()', self.mapperExampleFile, 'map()')
    self.mraButton.connect('clicked()', self.mapperExampleFile, 'map()')
    self.t2Button.connect('clicked()', self.mapperExampleFile, 'map()')
    self.abortDownloadButton.connect('clicked()', self.onAbortDownloadData)

    self.mapperExampleConfig = qt.QSignalMapper()
    self.mapperExampleConfig.connect('mapped(const QString&)', self.onSaveConfigFile)
    self.mapperExampleConfig.setMapping(self.exampleLRButton, self.Algorithm["Low Rank/Sparse Decomposition"])
    self.mapperExampleConfig.setMapping(self.exampleUABButton, self.Algorithm["Unbiased Atlas Creation"])
    self.mapperExampleConfig.setMapping(self.exampleNGLRAButton, self.Algorithm["Low Rank Atlas Creation"])
    self.exampleLRButton.connect('clicked()', self.mapperExampleConfig, 'map()')
    self.exampleUABButton.connect('clicked()', self.mapperExampleConfig, 'map()')
    self.exampleNGLRAButton.connect('clicked()', self.mapperExampleConfig, 'map()')

    # Refresh Apply button state
    self.onSelect()

  def onDownloadData(self,name):
    result = qt.QMessageBox.question(slicer.util.mainWindow(),
                                     'Download', "Downloading data might take several minutes",
                                      qt.QMessageBox.Ok, qt.QMessageBox.Cancel)
    if result == qt.QMessageBox.Cancel:
      return
    try:
      self.initProcessGUI()
      self.logic.downloadData(name)
    except Exception as e:
      logging.warning(e)
      self.onLogicRunStop()

  def onAbortDownloadData(self):
    if self.logic:
      logging.info("Download will stop after current file.")
      self.logic.abort = True

  def logEvent(self):
    self.logMessage(self.errorLog.logEntryDescription(self.errorLog.logEntryCount() - 1))

  def logMessage(self, message):
    self.log.setText(str(message))
    self.log.ensureCursorVisible()

  def onSelectFile(self):
    self.configFile = qt.QFileDialog.getOpenFileName(parent=self,caption='Select file')
    self.selectedConfigFile.text = self.configFile
    self.onSelect()

  def onSaveConfigFile(self, algo):
    file = qt.QFileDialog.getSaveFileName(parent=self,caption='Select file')
    if file:
      self.initProcessGUI()
      self.logic.CreateExampleConfigurationFile(file, self.BullseyeFileName, algo)
    self.onLogicRunStop()
    qt.QMessageBox.warning(slicer.util.mainWindow(),
                          'Download data',
                          'To use this configuration file, you will need to download the synthetic data')

  def initProcessGUI(self):
    self.progress_bar.start()
    sa = slicer.util.findChildren(name='ScrollArea')[0]
    vs = sa.verticalScrollBar()
    vs.setSliderPosition(vs.maximum)
    self.errorLog.connect('entryAdded(ctkErrorLogLevel::LogLevel)', self.logEvent)

  def cleanup(self):
    self.resetUI()
    if self.logic:
      self.logic.abort = True
    self.configFile = None
    self.selectedConfigFile.text = ''

  def onSelect(self):
    self.applyButton.enabled = self.configFile and self.selectAlgorithm.checkedButton()

  def resetUI(self):
    self.errorLog.disconnect('entryAdded(ctkErrorLogLevel::LogLevel)', self.logEvent)
    self.progress_bar.clear()

  def onApplyButton(self):
    try:
      self.initProcessGUI()
      self.logic.run(self.configFile,
                     self.Algorithm[self.selectAlgorithm.checkedButton().text],
                     self.inputSelector.currentNode())
    except Exception as e:
      logging.warning(e)
      self.onLogicRunStop()

  def onLogicRunStop(self):
    self.resetUI()
    self.logic.post_queue_stop_delayed()

#
# LowRankImageDecompositionLogic
#

class LowRankImageDecompositionLogic(ScriptedLoadableModuleLogic):
  """
  Class to download example data, create example configuration files, and run pyLAR algorithm (low-rank decomposition,
  unbiased atlas building, and low-rank atlas creation).
  The method downloading the data from a Midas server (URL and files to download are store in a JSON file) and
  running the pyLAR algorithms are multithreaded using the method implemented in [1]. This allows the Slicer GUI
  to stay responsive while one of these operation is performed. Since Slicer creashes if new data is loaded from
  a thread that is not the main thread, the new thread only performs computation and file management operations.
  Images computed or downloaded in the secondary thread are past to the main thread through a queue that loads the images
  using a QTimer.

  [1] https://github.com/SimpleITK/SlicerSimpleFilters/blob/master/SimpleFilters/SimpleFilters.py#L333-L514
  """
  def __init__(self):
    self.main_queue = Queue.Queue()
    self.main_queue_running = False
    self.post_queue = Queue.Queue()
    self.post_queue_running = False
    self.post_queue_timer = qt.QTimer()
    self.post_queue_interval = 0.5  # 0.5 second intervals
    self.post_queue_timer.setInterval(self.post_queue_interval)
    self.post_queue_timer.connect('timeout()', self.post_queue_process)
    self.thread = threading.Thread()
    self.abort = False

  def __del__(self):
    logging.debug("deleting logic")
    if self.main_queue_running:
      self.main_queue_stop()
    if self.post_queue_running:
      self.post_queue_stop()
    if self.thread.is_alive():
      self.thread.join()

  def yieldPythonGIL(self, seconds=0):
    sleep(seconds)

  def thread_doit(self, f, *args, **kwargs):
    try:
      if callable(f):
        f(*args, **kwargs)
      else:
        logging.error("Not a callable.")

    except Exception as e:
      msg = e.message
      self.abort = True

      self.yieldPythonGIL()
      # raise is a statement, we need a function to raise an exception
      # Solution found here:
      # http://stackoverflow.com/questions/8294618/define-a-lambda-expression-that-raises-an-exception
      self.main_queue.put(lambda :(_ for _ in ()).throw(Exception(e)))
    finally:
      self.main_queue.put(self.main_queue_stop)

  def main_queue_start(self):
    """Begins monitoring of main_queue for callables"""
    self.main_queue_running = True
    qt.QTimer.singleShot(0, self.main_queue_process)

  def post_queue_start(self):
    """Begins monitoring of main_queue for callables"""
    self.post_queue_running = True
    self.post_queue_timer.start()

  def post_queue_process(self):
    loader = slicer.util.loadVolume
    if not loader:
      logging.warning("No loader available.")
      return
    while not self.post_queue.empty():
      try:
        if self.abort:
          break
        name,filepath = self.post_queue.get_nowait()
        logging.info('Loading %s...' % (name,))
        if loader(filepath):
          logging.info('done loading %s...' % (name,))
        else:
          logging.warning('Error loading %s...' % (name,))
      except Queue.Empty:
        logging.debug("No file in post_queue to load.")

  def post_queue_stop_delayed(self):
    """
    Stops the post_queue_timer with a delay long enough to run it one last time.
    This is useful when one wants the final post processing to be performed after
    the thread is finished and tried to stop post_queue_timer
    """
    qt.QTimer.singleShot(self.post_queue_interval*2.0, self.post_queue_stop)

  def post_queue_stop(self):
    """End monitoring of post_queue for images"""
    self.post_queue_running = False
    self.post_queue_timer.stop()
    with self.post_queue.mutex:
      self.post_queue.queue.clear()
    logging.info("Done loading images")

  def main_queue_stop(self):
    """End monitoring of main_queue for callables"""
    self.main_queue_running = False
    if self.thread.is_alive():
      self.thread.join()
    slicer.modules.LowRankImageDecompositionWidget.onLogicRunStop()

  def main_queue_process(self):
    """processes the main_queue of callables"""
    try:
      while not self.main_queue.empty():
        f = self.main_queue.get_nowait()
        if callable(f):
          f()

      if self.main_queue_running:
        # Yield the GIL to allow other thread to do some python work.
        # This is needed since pyQt doesn't yield the python GIL
        self.yieldPythonGIL(.01)
        qt.QTimer.singleShot(0, self.main_queue_process)
    except Exception as e:
      logging.warning("Error in main_queue: \"{0}\"".format(e))

      # if there was an error try to resume
      if not self.main_queue.empty() or self.main_queue_running:
        qt.QTimer.singleShot(0, self.main_queue_process)

  def softwarePaths(self):
    savedPATH = os.environ["PATH"]
    currentFilePath = os.path.dirname(os.path.realpath(__file__))
    upDirectory = os.path.realpath(os.path.join(currentFilePath, '..'))
    # Prepend PATH with path of executables packaged with extension
    os.environ["PATH"] = os.path.join(upDirectory, 'ExternalBin') + os.pathsep + savedPATH
    # Creates software configuration file
    software = type('obj', (object,), {})
    slicerSoftware = ['BRAINSFit', 'BRAINSDemonWarp', 'BSplineDeformableRegistration', 'BRAINSResample',
                      'antsRegistration', 'AverageImages', 'ComposeMultiTransform', 'WarpImageMultiTransform',
                      'CreateJacobianDeterminantImage', 'InvertDeformationField']
    for i in slicerSoftware:
      setattr(software, 'EXE_'+str(i), find_executable(i))
    os.environ["PATH"] = savedPATH
    return software

  def run(self, configFile, algo, node = None):
    """
    Run the actual algorithm
    """
    # Check that pyLAR is not already running:
    try:
      if self.thread.is_alive():
        logging.warning("Processing is already running")
        return
    except AttributeError:
      pass
    # Create software configuration object
    config = pyLAR.loadConfiguration(configFile, 'config')
    software = self.softwarePaths()
    pyLAR.containsRequirements(config, ['data_dir', 'file_list_file_name', 'result_dir'], configFile)
    result_dir = config.result_dir
    data_dir = config.data_dir
    file_list_file_name = config.file_list_file_name
    im_fns = pyLAR.readTxtIntoList(os.path.join(data_dir, file_list_file_name))
    # 'clean' needs to be done before configuring the logger that creates a file in the output directory
    if hasattr(config, "clean") and config.clean:
        shutil.rmtree(result_dir)
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    pyLAR.configure_logger(logger, config, configFile)
    # If node given, save node on disk to run script
    # result_dir is created while configuring logger if it did not exist before
    if node:
      extra_image_file_name = os.path.join(result_dir, "ExtraImage.nrrd")
      slicer.util.saveNode(node, extra_image_file_name)
      config.selection.append(len(im_fns))
      im_fns.append(extra_image_file_name)
    ########################
    self.abort = False
    self.thread = threading.Thread(target=self.thread_doit,
                                   args=(self.pyLAR_run_thread, algo, config, software, im_fns, result_dir),
                                   kwargs={'configFN':configFile, 'file_list_file_name':file_list_file_name})

    self.main_queue_start()
    self.post_queue_start()
    self.thread.start()

  def pyLAR_run_thread(self, algo, config, software, im_fns, result_dir,
                      configFN, file_list_file_name):
    pyLAR.run(algo, config, software, im_fns, result_dir,
              configFN=configFN, file_list_file_name=file_list_file_name)
    list_images = pyLAR.readTxtIntoList(os.path.join(result_dir,'list_outputs.txt'))
    for i in list_images:
      name=os.path.splitext(os.path.basename(i))[0]
      self.post_queue.put((name,i))

  def loadDataFile(self, filename):
    """
    Returns
    -------
    downloads: List of the names of the bull's eye images available on http://slicer.kitware.com/midas3
    with their corresponding item number.
    """
    file_path = os.path.realpath(__file__)
    dir_path = os.path.dirname(file_path)
    dir_path = os.path.join(dir_path, 'Data')
    data = open(os.path.join(dir_path, filename), 'r').read()
    return json.loads(data)

  def loadImages(self, file_list):
    loader = slicer.util.loadVolume
    if loader:
      for name in file_list:
        logging.info('Loading %s...' % (name,))
        loader(filePath)

  def downloadData_thread(self, filename):
    """
    Downloads data based on the information provided in filename (JSON). It must contain
    a key called 'url' and a j=key called 'files'. See example files in 'Data' directory
    """
    logging.info('Starting to download')
    downloads = self.loadDataFile(filename)
    logging.debug("downloads:"+str(downloads))
    import socket
    socket.setdefaulttimeout(50)
    import urllib
    if 'url' not in downloads.keys():
      raise Exception("Key 'url' is missing in dictionary")
    url = downloads['url']
    if 'files' not in downloads.keys():
      raise Exception("Key 'files' is missing in dictionary")
    for name, value in downloads['files'].items():
      if self.abort:
        raise Exception("Download aborted")
      item_url = url + value
      filePath = os.path.join(slicer.app.settings().value('Cache/Path'), name)
      if not os.path.exists(filePath)\
              or slicer.app.settings().value('Cache/ForceRedownload') != 'false'\
              or os.stat(filePath).st_size == 0:
        logging.info('Requesting download %s\nfrom %s...\n' %(filePath, item_url))
        urllib.urlretrieve(item_url, filePath)
      self.post_queue.put((name,filePath))
    logging.info('Finished with download')

  def downloadData(self, filename):
    # Check that pyLAR is not already running:
    try:
      if self.thread.is_alive():
        logging.warning("Processing is already running")
        return
    except AttributeError:
      pass
    self.abort = False
    self.thread = threading.Thread(target=self.thread_doit,
                                   args=(self.downloadData_thread, filename))
    self.main_queue_start()
    self.post_queue_start()
    self.thread.start()

  def CreateExampleConfigurationFile(self, filename, datafile, download, algo):
    if download:
      data_dict = self.downloadData(datafile)
    else:
      data_dict = self.loadDataFile(datafile)
    config_data = type('config_obj', (object,), {'modality':'Simu'})()
    file_list_file_name = os.path.join(slicer.app.temporaryPath, "fileList.txt")
    data_list = data_dict['files'].keys()
    for i in range(0,len(data_list)):
      data_list[i] = os.path.join(slicer.app.temporaryPath, data_list[i])
    pyLAR.writeTxtFromList(file_list_file_name, data_list)
    config_data.file_list_file_name = "'"+file_list_file_name+"'"
    data_dir = slicer.app.temporaryPath
    config_data.data_dir = "'"+data_dir+"'"
    config_data.reference_im_fn = "'"+data_list[0]+"'"
    config_data.modality = 'Simu'
    config_data.lamda = 2.0
    config_data.verbose = 'True'
    config_data.result_dir = "'"+os.path.join(data_dir,'output')+"'"
    config_data.selection = [1,2,3]
    config_data.ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS = 2
    if algo == 'lr':  # Low-rank
      config_data.registration = 'affine'
      config_data.histogram_matching = 'False'
      config_data.sigma = 0
    else:
      config_data.num_of_iterations_per_level = 4
      config_data.num_of_levels = 1
      config_data.number_of_cpu = 2
      config_data.ants_params = {'Convergence' : '[100x50x25,1e-6,10]',\
          'Dimension': 3,\
          'ShrinkFactors' : '4x2x1',\
          'SmoothingSigmas' : '2x1x0vox',\
          'Transform' :'SyN[0.1,1,0]',\
          'Metric': 'MeanSquares[fixedIm,movingIm,1,0]'}
      if algo == 'nglra':  # Non-Greedy Low-rank altas creation
        config_data.use_healthy_atlas = 'False'
        config_data.sigma = 0
        config_data.registration_type = 'ANTS'
      elif algo == 'uab':  # Unbiased Atlas Creation
        pass
      else:
        raise Exception('Unknown algorithm to create configuration file')
    pyLAR.saveConfiguration(filename, config_data)



class LowRankImageDecompositionTest(ScriptedLoadableModuleTest):
  """
  This is the test case for your scripted module.
  Uses ScriptedLoadableModuleTest base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def setUp(self):
    """ Do whatever is needed to reset the state - typically a scene clear will be enough.
    """
    slicer.mrmlScene.Clear(0)

  def runTest(self):
    """Run as few or as many tests as needed here.
    """
    self.setUp()
    self.test_LowRankImageDecomposition1()

  def test_LowRankImageDecomposition1(self):
    """ Ideally you should have several levels of tests.  At the lowest level
    tests should exercise the functionality of the logic with different inputs
    (both valid and invalid).  At higher levels your tests should emulate the
    way the user would interact with your code and confirm that it still works
    the way you intended.
    One of the most important features of the tests is that it should alert other
    developers when their changes will have an impact on the behavior of your
    module.  For example, if a developer removes a feature that you depend on,
    your test should break so they know that the feature is needed.
    """

    self.delayDisplay("Starting the test")
    #
    # first, get some data
    #
    import urllib
    downloads = (
        ('http://slicer.kitware.com/midas3/download?items=231227', 'fMeanSimu.nrrd', slicer.util.loadVolume),
        )

    for url,name,loader in downloads:
      filePath = slicer.app.temporaryPath + '/' + name
      if not os.path.exists(filePath) or os.stat(filePath).st_size == 0:
        logging.info('Requesting download %s from %s...\n' % (name, url))
        urllib.urlretrieve(url, filePath)
      if loader:
        logging.info('Loading %s...' % (name,))
        loader(filePath)
    self.delayDisplay('Finished with download and loading')

    volumeNode = slicer.util.getNode(pattern="FA")
    logic = LowRankImageDecompositionLogic()
    self.assertTrue( logic.hasImageData(volumeNode) )
    self.delayDisplay('Test passed!')
