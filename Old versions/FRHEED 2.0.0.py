from PyQt5 import QtCore, QtGui, uic, QtWidgets
import sys
import cv2
import numpy as np
import threading
import time
import queue
import os
import pyqtgraph as pg
from scipy.fftpack import rfft
from PIL import Image, ImageQt
import PySpin
from matplotlib import cm
from colormap import Colormap

#### Define global variables ####
running = False
capture_thread = None
isfile = False
recording = False
setout = False
liveplotting = False
drawing = False
fileselected = False
sampletextset = False
growerset = False
grower = "None"
samplenum = "None"
imnum = 1
vidnum = 1
exposure = float(10000.0)# value in microseconds
avg = 0
t0 = time.time()
t, avg1, avg2, avg3, oldt, oldavg1, oldavg2, oldavg3, oldert, olderavg1, olderavg2, olderavg3 = [], [], [], [], [], [], [], [], [], [], [], []
x1, y1, x2, y2 = 0, 0, 640, 480
a1, b1, a2, b2 = 0, 0, 640, 480
c1, d1, c2, d2 = 0, 0, 640, 480
i = 1
red, green, blue = True, False, False
path = 'C:/Users/Palmstrom Lab/Desktop/FRHEED/'
filename = 'default'
#### Define colormap ####
cmp = Colormap()
FRHEEDcmap = cmp.cmap_linear('black', 'green', 'white')
cm.register_cmap(name='RHEEDgreen', cmap = FRHEEDcmap)
cmap = cm.gray
#cmp.test_colormap(FRHEEDcmap)
#### Loading UI file from qt designer ####
form_class = uic.loadUiType("FRHEED backup.ui")[0]
#### Define "shortcut" for queue ####
q = queue.Queue()
#### Define video recording codec ####
fourcc = cv2.VideoWriter_fourcc(*'MP4V')
#### Set default appearance of plots ####
pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 0.0)
#### Connect to RHEED camera ####
system = PySpin.System.GetInstance()
cam_list = system.GetCameras()
cam = cam_list.GetBySerial("18434385")
nodemap_tldevice = cam.GetTLDeviceNodeMap()
cam.Init()
cam.ExposureAuto.SetValue(PySpin.ExposureAuto_Off)
cam.ExposureTime.SetValue(exposure) # exposure time in microseconds
time.sleep(0.01)
nodemap = cam.GetNodeMap()
node_acquisition_mode = PySpin.CEnumerationPtr(nodemap.GetNode("AcquisitionMode"))
node_acquisition_mode_continuous = node_acquisition_mode.GetEntryByName("Continuous")
acquisition_mode_continuous = node_acquisition_mode_continuous.GetValue()
node_acquisition_mode.SetIntValue(acquisition_mode_continuous)
cam.BeginAcquisition()  

#### Code for grabbing frames from camera in threaded loop ####
def grab(width, height, fps, queue):
    global grower, running, recording, path, filename, exposure, isfile, samplenum, vidnum, out, fourcc, setout, cam
    print('before running')
    while running:
        frame = {}        
        image_result = cam.GetNextImage()
        img = image_result.GetNDArray()
        frame["img"] = img        
        if queue.qsize() < 10:
            queue.put(frame)
            if recording:
                if not setout:
                    time.sleep(0.5)
                    setout = True
                out.write(img)
        else:
            print(queue.qsize())

#### Programming main window ####
class FRHEED(QtWidgets.QMainWindow, form_class):
    def __init__(self, parent=None):
        global samplenum, exposure, x1, y1, x2, y2, grower
        QtWidgets.QMainWindow.__init__(self, parent)
        self.setupUi(self)
        #### Setting menu actions ####
        self.connectButton.clicked.connect(self.connectCamera)
        self.menuExit.triggered.connect(self.closeEvent)
        self.captureButton.clicked.connect(self.capture_image)
        self.recordButton.clicked.connect(self.record)
        self.liveplotButton.clicked.connect(self.liveplot)
        self.drawButton.clicked.connect(self.showShapes)
        self.changeExposure.valueChanged.connect(self.setExposure)
        self.rectButton.clicked.connect(self.selectColor)
        self.rectButton.setStyleSheet('QPushButton {color:red}')
        self.annotateLayer.setStyleSheet('QLabel {color:white}')
        self.annotateMisc.setStyleSheet('QLabel {color:white}')
        self.annotateOrientation.setStyleSheet('QLabel {color:white}')
        self.annotateSampleName.setStyleSheet('QLabel {color:white}')
        self.fftButton.clicked.connect(self.plotFFT)
        self.growerButton.clicked.connect(self.changeGrower)
        self.sampleButton.clicked.connect(self.changeSample)
        self.savenotesButton.clicked.connect(self.saveNotes)
        self.clearnotesButton.clicked.connect(self.clearNotes)
        self.redpeakLabel.hide()
        self.greenpeakLabel.hide()
        self.bluepeakLabel.hide()
        self.grayscaleButton.clicked.connect(self.mapGray)
        self.grayscaleSample.setPixmap(QtGui.QPixmap('gray colormap.png'))
        self.greenButton.clicked.connect(self.mapGreen)
        self.greenSample.setPixmap(QtGui.QPixmap('green colormap.png'))
        self.hotButton.clicked.connect(self.mapHot)
        self.hotSample.setPixmap(QtGui.QPixmap('hot colormap.png'))
        #### Size and identity of camera frame ####
        self.window_width = self.cameraCanvas.frameSize().width()
        self.window_height = self.cameraCanvas.frameSize().height()
        #### Create window for live data plotting ####
        self.plot1.plotItem.showGrid(True, True)
        self.plot1.plotItem.setContentsMargins(0,4,10,0)
        self.plot1.setLimits(xMin=0)
        self.plot1.setLabel('bottom', 'Time (s)')
        self.proxy = pg.SignalProxy(self.plot1.scene().sigMouseMoved, rateLimit=60, slot=self.mouseMoved)
        
        self.plot2.plotItem.showGrid(True, True)
        self.plot2.plotItem.setContentsMargins(0,4,10,0)
        self.plot2.setLimits(xMin=0)
        self.plot2.setLabel('bottom', 'Time (s)')
        
        self.plot3.plotItem.showGrid(True, True)
        self.plot3.plotItem.setContentsMargins(0,4,10,0)
        self.plot3.setLimits(xMin=0)
        self.plot3.setLabel('bottom', 'Time (s)')
        #### Create window for FFT plot ####
        self.plotFFTred.plotItem.showGrid(True, True)
        self.plotFFTred.plotItem.setContentsMargins(0,4,10,0)
        self.plotFFTred.setLabel('bottom', 'Frequency (Hz)')
        self.plotFFTgreen.plotItem.showGrid(True, True)
        self.plotFFTgreen.plotItem.setContentsMargins(0,4,10,0)
        self.plotFFTgreen.setLabel('bottom', 'Frequency (Hz)')
        self.plotFFTblue.plotItem.showGrid(True, True)
        self.plotFFTblue.plotItem.setContentsMargins(0,4,10,0)
        self.plotFFTblue.setLabel('bottom', 'Frequency (Hz)')
        #### Set 1 second timer before connecting to camera ####
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(1) #time in milliseconds
                
    #### Start grabbing camera frames when Camera -> Connect is clicked ####
    def connectCamera(self):
        global running, grower, isfile, samplenum, path, imnum, vidnum, growerset
        if not growerset:
            grower, ok = QtWidgets.QInputDialog.getText(w, 'Enter grower', 'Who is growing? ')
            if ok:
                imnum, vidnum = 1, 1
                growerset = True
                path = str('C:/Users/Palmstrom Lab/Desktop/FRHEED/'+grower+'/')
            else:
                QtWidgets.QMessageBox.warning(self, 'Error', 'Grower not set')
                return
        if not isfile:  
            samplenum, ok = QtWidgets.QInputDialog.getText(w, 'Change sample name', 'Enter sample name: ')
            if ok:
                imnum, vidnum = 1, 1
                isfile = True
                path = str('C:/Users/Palmstrom Lab/Desktop/FRHEED/'+grower+'/'+samplenum+'/')
                #### Create folder to save images in if it doesn't already exist ####
                if not os.path.exists(path):
                    os.makedirs(path)
            else:
                QtWidgets.QMessageBox.warning(self, 'Error', 'Grower not set')
                return
        running = True
        capture_thread.start()
        self.connectButton.setEnabled(False)
        self.connectButton.setText('Connecting...')
        self.statusbar.showMessage('Starting camera...')
        
    #### Change camera exposure ####
    def setExposure(self):
        global exposure, cam
        expo = self.changeExposure.value()
        exposure = float(500*2**expo) # Exponential scale for exposure (time in microseconds)
        cam.ExposureTime.SetValue(exposure)
        
    #### Protocol for updating the video frames in the GUI ####
    def update_frame(self):
        global avg1, avg2, avg3, t0, t, p, x1, y1, x2, y2, a1, b1, a2, b2, c1, d1, c2, d2, samplenum, grower, sampletextset, cmap
        if not q.empty():
            self.connectButton.setText('Connected')
            frame = q.get()
            img = frame["img"]
            img = np.flipud(img)
            img_height, img_width = img.shape
            #### Scaling the image from the camera ####
            scale_w = float(self.window_width) / float(img_width)
            scale_h = float(self.window_height) / float(img_height)
            scale = min([scale_w, scale_h])
            scale = 2
            if scale == 0:
                scale = 1
            if scale != 1:
                self.scaled_w = scale_w * img_width
                self.scaled_h = scale_h * img_height
                img = cv2.resize(img, dsize=(640, 480), interpolation=cv2.INTER_CUBIC)
                #### Apply colormap gist_earth ####
                imc = Image.fromarray(np.uint8(cmap(img)*255)) # colormaps: cm.gray, FRHEEDcmap, cm.Greens
                #### Convert PIL image to QImage
                imc = ImageQt.ImageQt(imc)
            #### Adding the camera to the screen ####
            self.cameraCanvas.setPixmap(QtGui.QPixmap.fromImage(imc))
            #### Updating live data ####
            if liveplotting:
                avg_1 = img[y1:y2, x1:x2].mean()
                avg_1 = round(avg_1, 3)
                avg_2 = img[b1:b2, a1:a2].mean()
                avg_2 = round(avg_2, 3)
                avg_3 = img[d1:d2, c1:c2].mean()
                avg_3 = round(avg_3, 3)
                avg1.append(avg_1)
                avg2.append(avg_2)
                avg3.append(avg_3)
                timenow = time.time() - t0
                t.append(timenow)
                pen1 = pg.mkPen('r', width=1, style=QtCore.Qt.SolidLine)
                pen2 = pg.mkPen('g', width=1, style=QtCore.Qt.SolidLine)
                pen3 = pg.mkPen('b', width=1, style=QtCore.Qt.SolidLine)
                curve1 = self.plot1.plot(pen=pen1, clear = True)
                curve2 = self.plot1.plot(pen=pen2)
                curve3 = self.plot1.plot(pen=pen3)
                curve1.setData(t, avg1)
                curve2.setData(t, avg2)
                curve3.setData(t, avg3)
#                pg.QtGui.QApplication.processEvents()
            if drawing:
                pixmap = QtGui.QPixmap(self.drawCanvas.frameGeometry().width(), self.drawCanvas.frameGeometry().height())
                pixmap.fill(QtGui.QColor("transparent"))
                qp = QtGui.QPainter(pixmap)
                qp.setPen(QtGui.QPen(QtCore.Qt.red, 2, QtCore.Qt.SolidLine))
                qp.drawRect(x1, y1, x2 - x1, y2 - y1)
                qp.setPen(QtGui.QPen(QtCore.Qt.green, 2, QtCore.Qt.SolidLine))
                qp.drawRect(a1, b1, a2 - a1, b2 - b1)
                qp.setPen(QtGui.QPen(QtCore.Qt.blue, 2, QtCore.Qt.SolidLine))
                qp.drawRect(c1, d1, c2 - c1, d2 - d1)
                qp.end()
                self.drawCanvas.setPixmap(pixmap)
        pixmap2 = QtGui.QPixmap(self.annotationCanvas.frameGeometry().width(), self.annotationCanvas.frameGeometry().height())
        pixmap2.fill(QtGui.QColor('black'))
        self.annotationCanvas.setPixmap(pixmap2)
        self.sampleLabel.setText('Current Sample: '+samplenum)
        self.growerLabel.setText('Current Grower: '+grower)
        self.annotateSampleName.setText('Sample: '+self.setSampleName.text())
        self.annotateOrientation.setText('Orientation: '+self.setOrientation.text())
        self.annotateLayer.setText('Growth layer: '+self.setGrowthLayer.text())
        self.annotateMisc.setText('Other notes: '+self.setMisc.text())
        if not sampletextset and samplenum != "None":
            self.setSampleName.setText(samplenum)
            sampletextset = True

    #### Saving a single image using the "Capture" button ####            
    def capture_image(self):
        global isfile, imnum, running, samplenum, path, filename
        if running:
            frame = q.get()
            img = frame["img"]
            img = cv2.resize(img, dsize=(640, 480), interpolation=cv2.INTER_CUBIC)
            #### Sequential file naming with timestamp ####
            imnum_str = str(imnum).zfill(2) # format image number as 01, 02, etc.
            timestamp = time.strftime("%b-%d-%Y %I.%M.%S %p") # formatting timestamp
            filename = samplenum+' '+imnum_str+' '+timestamp
            #### Save annotation ####
            a = self.annotationFrame.grab()
            a.save('annotation.jpg', 'jpg')
            #### Actually saving the file
            cv2.imwrite('picture.jpg', img)
            #### Splice images ####
            anno = Image.open('annotation.jpg')
            width1, height1 = anno.size
            pic = Image.open('picture.jpg')
            width2, height2 = pic.size
            w = width1
            h = height1 + height2
            image = Image.new('L', (w, h))
            image.paste(pic, (0,0))
            image.paste(anno, (0,height2))
            #### Save completed image ####
            image.save(path+filename+'.png')
            os.remove('annotation.jpg')
            os.remove('picture.jpg')
            #### Increase image number by 1 ####
            imnum = int(imnum) + 1
            self.statusbar.showMessage('Image saved to '+path+' as '+filename+'.png')
        #### Alert popup if you try to save an image when the camera is not running ####
        else:
            QtWidgets.QMessageBox.warning(self, 'Error', 'Camera is not running')
    
    #### Saving/recording video ####        
    def record(self):
        global recording, isfile, filename, path, samplenum, vidnum, out, fourcc
        recording = not recording
        if recording and running:
            self.statusbar.showMessage('Recording video...')
            self.recordButton.setText('Stop Recording')
            vidnum_str = str(vidnum).zfill(2)
            timestamp = time.strftime("%b-%d-%Y %I.%M.%S %p") # formatting timestamp
            filename = samplenum+' '+vidnum_str+' '+timestamp            
            vidnum = int(vidnum) + 1
            out = cv2.VideoWriter(path+filename+'.avi', fourcc, 35.0, (2048,1536), False) # native resolution is 2048 x 1536
        if not recording and running:
            self.statusbar.showMessage('Video saved to '+path+' as '+filename+'.avi')
            self.recordButton.setText('Record Video')
        if not running:
            QtWidgets.QMessageBox.warning(self, 'Error', 'Camera is not running')
            
    #### Live plotting intensity data ####
    def liveplot(self):
        global running, liveplotting, t0, avg1, avg2, avg3, t, oldert, olderavg1, olderavg2, olderavg3, oldt, oldavg1, oldavg2, oldavg3
        liveplotting = not liveplotting
        if running:
            if liveplotting:
                self.liveplotButton.setText('Stop Live Plot')
                t0 = time.time()
                self.statusbar.showMessage('Live plotting data...')
            else:
                self.liveplotButton.setText('Start Live Plot')
                self.statusbar.showMessage('Live plotting stopped')
                oldert = oldt
                olderavg1 = oldavg1
                olderavg2 = oldavg2
                olderavg3 = oldavg3
                oldt = t
                oldavg1 = avg1
                oldavg2 = avg2
                oldavg3 = avg3
                pen1 = pg.mkPen('r', width=1, style=QtCore.Qt.SolidLine)
                pen2 = pg.mkPen('g', width=1, style=QtCore.Qt.SolidLine)
                pen3 = pg.mkPen('b', width=1, style=QtCore.Qt.SolidLine)
                curve1 = self.plot2.plot(pen=pen1, clear = True)
                curve2 = self.plot2.plot(pen=pen2)
                curve3 = self.plot2.plot(pen=pen3)
                curve1.setData(oldt, oldavg1)
                curve2.setData(oldt, oldavg2)
                curve3.setData(oldt, oldavg3)
                curve4 = self.plot3.plot(pen=pen1, clear = True)
                curve5 = self.plot3.plot(pen=pen2)
                curve6 = self.plot3.plot(pen=pen3)
                curve4.setData(oldert, olderavg1)
                curve5.setData(oldert, olderavg2)
                curve6.setData(oldert, olderavg3)
                t = []
                avg1 = []
                avg2 = []
                avg3 = []
        else:
            QtWidgets.QMessageBox.warning(self, 'Error', 'Camera is not running')
            
    #### Show or hide shapes ####
    def showShapes(self):
        global drawing
        drawing = not drawing
        if drawing:
            self.drawCanvas.show()
            self.drawButton.setText('Hide Shapes')
        if not drawing:
            self.drawCanvas.hide()
            self.drawButton.setText('Show Shapes')
            
    #### Record position of mouse when you click the button ####        
    def mousePressEvent(self, event: QtGui.QMouseEvent):
        global x1, y1, x2, y2, a1, b1, a2, b2, c1, d1, c2, d2, red, blue, yellow
        if self.drawCanvas.underMouse():
            if red:
                x1, y1 = event.pos().x()-10, event.pos().y()-70
            if green:
                a1, b1 = event.pos().x()-10, event.pos().y()-70
            if blue:
                c1, d1 = event.pos().x()-10, event.pos().y()-70
                
    #### Record position of mouse when you release the button ####    
    def mouseReleaseEvent(self, event: QtGui.QMouseEvent):
        global x1, y1, x2, y2, a1, b1, a2, b2, c1, d1, c2, d2, red, blue, green
        if self.drawCanvas.underMouse():
            if red:
                x2, y2 = event.pos().x()-10, event.pos().y()-70
            if green:
                a2, b2 = event.pos().x()-10, event.pos().y()-70
            if blue:
                c2, d2 = event.pos().x()-10, event.pos().y()-70
                
    #### Change which rectangle color you're editing ####            
    def selectColor(self):
        global red, green, blue, i
        i +=1
        if i == 4:
            i = 1
        if i == 1:
            self.rectButton.setStyleSheet('QPushButton {color: red}')
            self.rectButton.setText('Editing Red')
            red, green, blue = True, False, False
        if i == 2:
            self.rectButton.setStyleSheet('QPushButton {color: green}')
            self.rectButton.setText('Editing Green')
            red, green, blue = False, True, False
        if i == 3:
            self.rectButton.setStyleSheet('QPushButton {color: blue}')
            self.rectButton.setText('Editing Blue')
            red, green, blue = False, False, True
            
    #### Plot FFT of most recent data ####
    def plotFFT(self):
        global fileselected, oldt, oldavg1, oldavg2, oldavg3
        if not fileselected:
            #### Plot FFT of data from red rectangle ####
            t_length = len(oldt)
            dt = (max(oldt) - min(oldt))/(t_length-1)
            red_no_dc = oldavg1 - np.mean(oldavg1)
            yf1 = rfft(red_no_dc)
            tf = np.linspace(0.0, 1.0/(2.0*dt), t_length//2)
            i = np.argmax(abs(yf1[0:t_length//2]))
            redpeak = tf[i]
            peakfind1=str('Peak at '+str(round(redpeak, 2))+' Hz or '+str(round(1/redpeak, 2))+' s')
            self.redpeakLabel.setText(peakfind1)
            pen1 = pg.mkPen('r', width=1, style=QtCore.Qt.SolidLine)
            self.plotFFTred.plot(tf, np.abs(yf1[0:t_length//2]), pen=pen1, clear = True)
            #### Plot FFT of data from green rectangle ####
            green_no_dc = oldavg2 - np.mean(oldavg2)
            yf2 = rfft(green_no_dc)
            j = np.argmax(abs(yf2[0:t_length//2]))
            greenpeak = tf[j]
            peakfind2=str('Peak at '+str(round(greenpeak, 2))+' Hz or '+str(round(1/greenpeak, 2))+' s')
            self.greenpeakLabel.setText(peakfind2)
            pen2 = pg.mkPen('g', width=1, style=QtCore.Qt.SolidLine)
            self.plotFFTgreen.plot(tf, np.abs(yf2[0:t_length//2]), pen=pen2, clear = True)
            #### Plot FFT of data from blue rectangle ####
            blue_no_dc = oldavg3 - np.mean(oldavg3)
            yf3 = rfft(blue_no_dc)
            k = np.argmax(abs(yf3[0:t_length//2]))
            bluepeak = tf[k]
            peakfind3=str('Peak at '+str(round(bluepeak, 2))+' Hz or '+str(round(1/bluepeak, 2))+' s')
            self.bluepeakLabel.setText(peakfind3)
            pen3 = pg.mkPen('b', width=1, style=QtCore.Qt.SolidLine)
            self.plotFFTblue.plot(tf, np.abs(yf3[0:t_length//2]), pen=pen3, clear = True) 
            #### Show labels for peak positions ####
            self.redpeakLabel.show()
            self.greenpeakLabel.show()
            self.bluepeakLabel.show()
            
    #### Change sample ####
    def changeSample(self):
        global samplenum, grower, path, imnum, vidnum, isfile
        samplenum, ok = QtWidgets.QInputDialog.getText(w, 'Change sample name', 'Enter sample name: ')
        if ok:
            isfile = True
            print(samplenum)
            imnum, vidnum = 1, 1
            self.sampleLabel.setText('Current Sample: '+samplenum)
            path = str('C:/Users/Palmstrom Lab/Desktop/FRHEED/'+grower+'/'+samplenum+'/')
            #### Create folder to save images in if it doesn't already exist ####
            if not os.path.exists(path):
                os.makedirs(path)
                print(path+' created')
                
    #### Change grower ####
    def changeGrower(self):
        global samplenum, grower, path, imnum, vidnum, growerset
        grower, ok = QtWidgets.QInputDialog.getText(w, 'Change grower', 'Who is growing? ')
        if ok:
            growerset = True
            imnum, vidnum = 1, 1
            self.growerLabel.setText('Current Grower: '+grower)
            path = str('C:/Users/Palmstrom Lab/Desktop/FRHEED/'+grower+'/'+samplenum+'/')
            #### Create folder to save images in if it doesn't already exist ####
            if not os.path.exists(path):
                os.makedirs(path)
                
    #### Saving notes ####
    def saveNotes(self):
        global path, filename
        timestamp = time.strftime("%b-%d-%Y %I.%M.%S %p") # formatting timestamp
        if not os.path.exists(path):
            os.makedirs(path)
        with open(path+'Growth notes '+timestamp+'.txt', 'w+') as file:
            file.write(str(self.noteEntry.toPlainText()))
        self.statusbar.showMessage('Notes saved to '+path+' as '+'Growth notes '+timestamp+'.txt')
        
    #### Clearing notes ####
    def clearNotes(self):
        reply = QtGui.QMessageBox.question(w, 'Caution', 'Are you sure you want to clear all growth notes?', QtGui.QMessageBox.Yes, QtGui.QMessageBox.No)
        if reply == QtGui.QMessageBox.Yes:
            self.noteEntry.clear()
        if reply == QtGui.QMessageBox.No:
            pass
        
    #### Set colormaps ####
    def mapGray(self):
        global cmap
        cmap = cm.gray
    def mapGreen(self):
        global cmap
        cmap = FRHEEDcmap
    def mapHot(self):
        global cmap
        cmap = cm.hot
        
    #### Mouse tracking on graphs ####
    def mouseMoved(self, evt):
        mousePoint = self.plot1.vb.mapSceneToView(evt[0])
        x = mousePoint.x()
        y = mousePoint.y()
        print(x, y)
        self.cursorLabel1.setText('x = '+round(x,3)+', y = '+round(y,3))
        """
        i think i need to switch the plots from PlotItems to GraphicsWindows with addPlots to them
        """
        
    #### Close the program and terminate threads ####            
    def closeEvent(self, event):
        global running, cam
        running = False
        print('Shutting down...')
        cam.EndAcquisition()
        cam.DeInit()
        del cam
        cam_list.Clear()
        system.ReleaseInstance()
        self.close()
        capture_thread.terminate()

#### Initialize threading with arguments for camera source, queue, frame dimensions and FPS ####
capture_thread = threading.Thread(target=grab, args = (2048, 1536, 35, q)) # RHEED camera is 2048 by 1536

#### Run the program, show the main window and name it 'FRHEED' ####
app = QtWidgets.QApplication(sys.argv)
w = FRHEED(None)
w.setWindowTitle('FRHEED')
w.show()
app.exec_()

#### TODO: ####
"""
- add coordinates of mouse cursor on plots
- add 1D line plot for strain analysis
- add background subtraction
- fix bugs associated with startup crashes
"""
