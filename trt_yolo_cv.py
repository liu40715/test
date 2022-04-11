import os
import argparse

import cv2
import pycuda.autoinit  # This is needed for initializing CUDA driver
from PIL import Image,ImageDraw,ImageFont
from utils.yolo_with_plugins import TrtYOLO
import time
import json
import base64
from deep_sort import preprocessing
from deep_sort import nn_matching
from deep_sort.detection import Detection
from deep_sort.tracker import Tracker
from tools import generate_detections as gdet
import numpy as np
import threading
import paho.mqtt.client as mqtt
from collections import defaultdict
import datetime

class make_detectline():
    def __init__(self):
        self.point = []
        self.line = None
    def on_EVENT_LBUTTONDOWN(self,event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            self.point.append("{0},{1},".format(x, y))
            if len(self.point) == 2:
                self.line = "%s"%(self.point[0]+self.point[1])
                with open("save_linepoint.txt", 'w') as f:
                    f.write(self.line)
                self.point = []

    def draw_line(self,image,points):
        loop = True
        s1= 0
        c = 3
        cv2.setMouseCallback("output_style_full_screen", self.on_EVENT_LBUTTONDOWN)
        while(loop):
            display_img = image.copy()
            cv2.putText(display_img,"%s"%(c), (50,50),cv2.FONT_HERSHEY_COMPLEX_SMALL, 3, (0, 0, 255), 3)
            s2 = datetime.datetime.now().second
            if s2 - s1 == 1:
                c-=1
                if c == -1:
                    with open("save_linepoint.txt") as f:
                        line = f.readlines()[0]
                    line = [(int(line.split(",")[0]),int(line.split(",")[1])),(int(line.split(",")[2]),int(line.split(",")[3]))]
                    loop = False
            s1 = s2
            if self.line != None:
                line = [(int(self.line.split(",")[0]),int(self.line.split(",")[1])),(int(self.line.split(",")[2]),int(self.line.split(",")[3]))]
                cv2.line(display_img,line[0], line[1], (0, 0, 255), 5)
                loop = False
            cv2.imshow("output_style_full_screen",display_img)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                with open("save_linepoint.txt") as f:
                    line = f.readlines()[0]
                line = [(int(line.split(",")[0]),int(line.split(",")[1])),(int(line.split(",")[2]),int(line.split(",")[3]))]
                with open("p_ount_data.txt", 'w') as f:
                    f.write("0,0")
                loop = False
            #繪製遮罩
            img_bg = np.zeros((display_img.shape[0], display_img.shape[1], 3), np.uint8)
            roi = cv2.fillPoly(img_bg, [points], [1,1,1])
        return line,roi

class People_counting():
    def __init__(self):
        self.mqtt_connect()
        self.c = np.random.rand(32, 3) * 255
        self.tracker,self.encoder= self.Deep_SORT()
        self.trt_yolo = TrtYOLO('yolov4-crowdhuman-416x416', 2, 'store_true')
        self.cam_frame = []
        self.receive_trigger = False
        self.send_delay = 0
        self.msg_trigger = True
        self.region_person = {"A1":0,"A2":0,"B1":0,"B2":0,"C1":0,"C2":0,"D1":0,"E1":0,"F1":0}
        self.warn_icon  = cv2.imread("warn_icon.png")
        self.attn_icon  = cv2.imread("littlecrowd.png")
        self.r_circle = cv2.imread("red_circle.jpg")
        self.y_circle = cv2.imread("brown.jpg")
        t = threading.Thread(target = self.ipcam)
        t.start()


    def on_connect(self,client, userdata, flags, rc):
        self,client.subscribe("agx_server")
        print("Connected with result code "+str(rc))##print出值為0代表連接成功

    def on_message(self,client, userdata, msg):
        # base64_decoded = base64.b64decode(msg.payload.decode('utf-8'))
        # nparr = np.frombuffer(base64_decoded, np.uint8)
        # img_np = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        # self.receive_img = cv2.resize(img_np, (1280, 960), interpolation=cv2.INTER_CUBIC)
        # self.receive_trigger = True
        try:
            mqttdata = msg.payload.decode('utf-8')
            mqttdata = json.loads(mqttdata)
            for i in mqttdata:
                self.region_person[i] = mqttdata[i]
            self.msg_trigger = True
        except:pass
		
    def mqtt_connect(self,):
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.connect('10.96.226.107',1883,60)
        self.client.loop_start()

    def ipcam(self,):
        # capture = cv2.VideoCapture("rtsp://admin:@10.88.33.129:554/h264/ch1/main/av_stream")
        capture = cv2.VideoCapture("rtsp://10.96.226.62:8080/stream1")
        # capture = cv2.VideoCapture("rtsp://cimadmin:cim123@10.88.32.85:88/videoMain")
        #frame = cv2.imread("Entrance.jpg")#測試
        while(True):
            ret,frame = capture.read()
            if ret == False: return False
            self.cam_frame = frame

    def Deep_SORT(self,):
        # Definition of the parameters
        max_cosine_distance = 0.4
        nn_budget = None
        # Deep SORT
        model_filename = './mars-small128.pb'
        encoder = gdet.create_box_encoder(model_filename, batch_size=1)
        metric = nn_matching.NearestNeighborDistanceMetric("cosine", max_cosine_distance, nn_budget)
        tracker = Tracker(metric)
        return tracker,encoder  

    def _box_process(self,boxes,confs,clss):
        new_boxes = []
        for bb, cf, cl in zip(boxes, confs, clss):
            if int(cl) != 1:continue
            x_min, y_min, x_max, y_max = bb[0], bb[1], bb[2], bb[3]
            x,y,w,h = int(x_min),int(y_min),int(x_max - x_min),int(y_max - y_min)
            if x < 0:
                w = w + x
                x = 0
            if y < 0:
                h = h + y
                y = 0
            new_boxes.append([x, y, w, h])
        return new_boxes

    def _dsort_detection(self,new_boxes, confs, clss, features):
        detections = [Detection(new_boxes, confs, clss, feature) for new_boxes, confs, clss, feature in
                    zip(new_boxes, confs, clss, features)]
        return detections

    def _dsort_max_suppression(self,detections):
        nms_max_overlap = 1.0
        boxes = np.array([d.tlwh for d in detections])
        scores = np.array([d.confidence for d in detections])
        indices = preprocessing.non_max_suppression(boxes, nms_max_overlap, scores)
        return indices

    def tracke_process(self,P_frame, boxes,confs, clss):
        new_boxes = self._box_process(boxes,confs,clss)
        features = self.encoder(P_frame, new_boxes)
        detections = self._dsort_detection(new_boxes, confs, clss, features)
        indices = self._dsort_max_suppression(detections)
        detections = [detections[i] for i in indices]
        return detections

    def cv2ImgAddText(self,img, text, x, textColor=(255, 255, 255), textSize=20):
        if (isinstance(img, np.ndarray)): 
            img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img)
        fontStyle = ImageFont.truetype("./NotoSansTC-Regular.otf", textSize, encoding="utf-8")
        draw.text(x, text, textColor, font=fontStyle)
        return cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2BGR)

    def dashboard(self,):
        background = np.ones((1080, 1920, 3), dtype="uint8")
        cv2.rectangle(background, (0,0),(1920,120),(89,89,89),-1)#title Bar
        background = self.cv2ImgAddText(background, "AI 即時現場人流計數", (30,20), textColor=(255, 255, 255), textSize=48)
        background = self.cv2ImgAddText(background, "AI 即時現場人流密度", (670,20), textColor=(255, 255, 255), textSize=48)
        heatmap = cv2.imread("heatmap_bg2.png")
        heatmap = cv2.resize(heatmap, (1280, 960), interpolation=cv2.INTER_CUBIC)

        mask_heatmap = heatmap.copy()
        #各區人流看板
        # mask_heatmap[0:200,0:320] = [0,0,0]
        # heatmap = cv2.addWeighted(mask_heatmap, 0.4, heatmap, 0.6,0)
        # heatmap = self.cv2ImgAddText(heatmap, "會場主舞台 : ",(10,10) , textColor=(255, 255, 255), textSize=20)
        # heatmap = self.cv2ImgAddText(heatmap, "OPEN AI : ", (10,40), textColor=(255, 255, 255), textSize=20)
        # heatmap = self.cv2ImgAddText(heatmap, "AI視覺機器人 : ", (10,70), textColor=(255, 255, 255), textSize=20)
        # heatmap = self.cv2ImgAddText(heatmap, "燈塔工廠 : ", (10,100), textColor=(255, 255, 255), textSize=20)
        # heatmap = self.cv2ImgAddText(heatmap, "智慧製造７大場景 : ", (10,130), textColor=(255, 255, 255), textSize=20)
        # heatmap = self.cv2ImgAddText(heatmap, "友安全承攬管理e把罩 : ", (10,160), textColor=(255, 255, 255), textSize=20)

        mask_heatmap[0:60,850:1280] = [0,0,0]
        heatmap = cv2.addWeighted(mask_heatmap, 0.4, heatmap, 0.6,0)
        here_icon = cv2.imread("here.png")
        heatmap = self.set_icon(heatmap,here_icon,(1190,450),50)
        heatmap = self.set_icon(heatmap,self.warn_icon,(870,30),30)
        heatmap = self.set_icon(heatmap,self.attn_icon,(1010,30),30)
        heatmap = self.set_icon(heatmap,here_icon,(1150,30),30)
        heatmap = self.cv2ImgAddText(heatmap, "人多壅擠", (890,10), textColor=(255, 255, 255), textSize=25)
        heatmap = self.cv2ImgAddText(heatmap, "人潮略多", (1030,10), textColor=(255, 255, 255), textSize=25)
        heatmap = self.cv2ImgAddText(heatmap, "現在位置", (1170,10), textColor=(255, 255, 255), textSize=25)

        #地圖
        heatmap = cv2.resize(heatmap, (1280, 960), interpolation=cv2.INTER_CUBIC)
        heatmap = self.cv2ImgAddText(heatmap, "會場主舞台", (740,440), textColor=(0, 0, 0), textSize=28)
        heatmap = self.cv2ImgAddText(heatmap, "Open AI", (1080,760), textColor=(0, 0, 0), textSize=28)
        heatmap = self.cv2ImgAddText(heatmap, "AI視覺機器人", (620,750), textColor=(0, 0, 0), textSize=28)
        heatmap = self.cv2ImgAddText(heatmap, "燈塔工廠", (680,140), textColor=(0, 0, 0), textSize=28)
        heatmap = self.cv2ImgAddText(heatmap, "　　智慧智造\n共創．聯邦式學習\n　　７大場景", (160,680), textColor=(0, 0, 0), textSize=24)
        heatmap = self.cv2ImgAddText(heatmap, "   友安全\n承攬管理\n   e把罩",  (400,420), textColor=(0, 0, 0), textSize=24)
        background[120:1080,640:1920] = heatmap

        cv2.rectangle(background, (0,480),(640,600),(89,89,89),-1)#參觀人數
        background = self.cv2ImgAddText(background, "今日參觀人數", (30,500), textColor=(255, 255, 255), textSize=48)
        cv2.rectangle(background, (0,600),(320,880),(150, 104, 0),-1)#參觀中人數
        background = self.cv2ImgAddText(background, "參觀中人數", (30,620), textColor=(255, 255, 255), textSize=36)
        cv2.rectangle(background, (320,600),(640,880),(89,89,89),-1)#已參加人數
        background = self.cv2ImgAddText(background, "已參觀人數", (350,620), textColor=(255, 255, 255), textSize=36)
        cv2.rectangle(background, (0,880),(640,1280),(89,89,89),-1)#時間顯示
        background = self.cv2ImgAddText(background, "Powered by", (280,1010), textColor=(255, 255, 255), textSize=24)
        logo = cv2.imread("auotalk.jpg")#217*47
        background[1003:1050,423:640] = logo
        return background

    def push_nodered(self,image):
        #因為傳送太快nodered會延遲刻意降低傳送速度
        #self.send_delay += 1
        #if fps >= 25:
        #  if self.send_delay == 10:
        #    byte1 = cv2.imencode('.jpg', image[0])[1].tobytes()
        #    byte2 = cv2.imencode('.jpg', image[1])[1].tobytes()
        #    byte3 = cv2.imencode('.jpg', image[2])[1].tobytes()
        #    self.client.publish("img1",byte1)
        #    self.client.publish("img2",byte2)
        #    self.client.publish("img3",byte3)
        #    self.send_delay = 0
        #else:
        #    byte1 = cv2.imencode('.jpg', image[0])[1].tobytes()
        #    byte2 = cv2.imencode('.jpg', image[1])[1].tobytes()
        #    byte3 = cv2.imencode('.jpg', image[2])[1].tobytes()
        #    self.client.publish("img1",byte1)
        #    self.client.publish("img2",byte2)
        #    self.client.publish("img3",byte3)
        byte1 = cv2.imencode('.jpg', image[0])[1].tobytes()
        byte2 = cv2.imencode('.jpg', image[1])[1].tobytes()
        byte3 = cv2.imencode('.jpg', image[2])[1].tobytes()
        self.client.publish("img1",byte1)
        self.client.publish("img2",byte2)
        self.client.publish("img3",byte3)

    def set_circle(self,bg,circle,pos,size):
        img_blank = np.zeros((bg.shape[0],bg.shape[1],3), dtype="uint8")
        circle = cv2.resize(circle, (size,size))
        img_blank[pos[1]-int(circle.shape[0]*0.5):pos[1]+int(circle.shape[0]*0.5),
                pos[0]-int(circle.shape[1]*0.5):pos[0]+int(circle.shape[1]*0.5)] = circle
        dst = cv2.addWeighted(bg, 1, img_blank,0.3,0)
        return dst

    def set_icon(self,bg,icon,pos,size):
        icon = cv2.resize(icon, (size,size))
        img2gray = cv2.cvtColor(icon,cv2.COLOR_BGR2GRAY)
        ret, mask = cv2.threshold(img2gray, 1, 255, cv2.THRESH_BINARY)
        mask = cv2.cvtColor(mask,cv2.COLOR_GRAY2BGR)
        rows, cols, channels = mask.shape
        roi = bg[pos[1]-round(rows*0.5):pos[1]+round(rows*0.5), pos[0]-round(cols*0.5):pos[0]+round(cols*0.5)]
        dst = cv2.subtract(roi,mask)
        kernel = np.ones((3,3), np.uint8) 
        dst = cv2.dilate(dst, kernel, iterations=1)
        dst = cv2.add(icon,dst)
        bg[pos[1]-round(rows*0.5):pos[1]+round(rows*0.5), pos[0]-round(cols*0.5):pos[0]+round(cols*0.5)] = dst
        return bg

    def warning_area(self,bg,circle_color,icon,pos,circle_size,icon_size):
        bg = self.set_circle(bg,circle_color,pos,circle_size)
        bg = self.set_icon(bg,icon,pos,icon_size)
        # if people == "crowded":
        #     bg = self.cv2ImgAddText(bg, "人多壅擠",(pos[0]-22,pos[1]-30), textColor=(255, 0, 0), textSize=10)
        # if people == "slightly":
        #     bg = self.cv2ImgAddText(bg, "人潮略多",(pos[0]-22,pos[1]-30), textColor=(255, 128, 0), textSize=10)
        return bg

    def heatmap_mask(self,img):
        bg = img.copy()
        # #看板區
        # A_region = self.region_person["A1"] + self.region_person["A2"]#AI視覺機器人
        # B_region = self.region_person["B1"] + self.region_person["B2"]#燈塔工廠
        # C_region = self.region_person["C1"] + self.region_person["C2"]#智慧製造
        # #========================攝影機照不到先留著=====================================
        # D_region = self.region_person["D1"]#會場主舞台
        # E_region = self.region_person["E1"]#OPENAI
        # F_region = self.region_person["F1"]#友安全
        # #=============================================================================

        # region_list = {"A_region":[A_region,(150,70)],"B_region":[B_region,(110,100)],"C_region":[C_region,(190,130)],
        #                 "D_region":[D_region,(130,10)],"E_region":[E_region,(110,40)],"F_region":[F_region,(220,160)]}
        # for i in region_list:
        #     if region_list[i][0] > 20:
        #         bg = self.cv2ImgAddText(bg, "人潮擁擠", region_list[i][1], textColor=(255, 0, 0), textSize=20)
        #     elif 20 >= region_list[i][0] > 10:
        #         bg = self.cv2ImgAddText(bg, "人潮略多", region_list[i][1], textColor=(255, 255, 0), textSize=20)
        #     else: 
        #         bg = self.cv2ImgAddText(bg, "人潮稀少", region_list[i][1], textColor=(0, 255, 0), textSize=20)
        #警示區
        mask = {"A1":[950,200],"A2":[500,200],"B1":[850,800],"B2":[450,800],"C1":[150,300],"C2":[150,700],"D1":[900,460],"E1":[1100,720],"F1":[430,460]}#1280,960
        for i in self.region_person:
            if self.region_person[i] >= 20:
                bg = self.warning_area(bg,self.r_circle,self.warn_icon,(mask[i][0],mask[i][1]),300,30)
            elif 20 > self.region_person[i] >=10:
                bg = self.warning_area(bg,self.y_circle,self.attn_icon,(mask[i][0],mask[i][1]),300,30)
        # result = cv2.addWeighted(bg, 0.3, img, 0.7, 0)
        return bg

    def loop_and_detect(self,conf_th):
        bg = self.dashboard()
        hm = bg[120:1080,640:1920]
        points = np.array([[60,679], [314,164], [962,188], [1181,691]])
        dir_n = defaultdict(list)
        check = {}
        dir_locate = {}
        enter = 0
        leave = 0
        fps = 0.0
        pred_size = 0.5 #縮小圖片
        out_win = "output_style_full_screen"
        cv2.namedWindow(out_win, cv2.WINDOW_NORMAL)
        cv2.setWindowProperty(out_win, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        md = make_detectline()
        with open("p_ount_data.txt") as f:
            p_ount = f.readlines()[0]
        enter,leave = int(p_ount.split(",")[0]),int(p_ount.split(",")[1])
        s1 = 0
        s3 = 0
        while True:
            # t1 = time.time()
            #將收到的圖片替換
            # if self.receive_trigger == True:
            #     recive_img = self.receive_img
            #     bg[120:1080,640:1920] = recive_img
            #     self.receive_trigger = False
            background = bg.copy()
            if self.msg_trigger == True:#確認人口密度
                try:
                    hm = self.heatmap_mask(bg[120:1080,640:1920])
                    self.msg_trigger = False
                except:
                    self.msg_trigger = False
            background[120:1080,640:1920] = hm
            if self.cam_frame != []:
                #繪製ROI區域
                roi_frame = cv2.polylines(self.cam_frame.copy(), pts=[points], isClosed=True, color=[0,0,255], thickness=2)
                frame = roi_frame.copy()
                show = roi_frame.copy()
                #畫判定線
                if 'dectect_line' not in locals():
                    dectect_line ,dectect_roi = md.draw_line(roi_frame,points)
                P_frame = self.cam_frame.copy()
                #進行ROI處理
                P_frame *= dectect_roi
                #將預測圖片resize加速預測
                P_frame = cv2.resize(P_frame, (round(self.cam_frame.shape[1]*pred_size),
                                    round(self.cam_frame.shape[0]*pred_size)), interpolation=cv2.INTER_CUBIC)

                # 設定界線
                cv2.line(show, (230,388), (1040,420), (255,255,255), 40)
                # cv2.line(show, dectect_line[0], dectect_line[1], (255,255,255), 20)
                dir_t,dir_y  = " "," "  
                boxes, confs, clss = self.trt_yolo.detect(P_frame, conf_th)

                detections = self.tracke_process(P_frame, boxes,confs, clss)
                self.tracker.predict()
                self.tracker.update(detections)
                for track in self.tracker.tracks:
                    if not track.is_confirmed() or track.time_since_update > 1: continue
                    bbox = track.to_tlbr()
                    bbox = bbox / pred_size #預測結果換算原尺寸
                    x_center = round((round(bbox[2]) - round(bbox[0]))/2+round(bbox[0]))
                    y_center = round((round(bbox[3]) - round(bbox[1]))/2+round(bbox[1]))

                    #先給空值
                    if str(track.track_id) not in dir_locate:
                        dir_locate[str(track.track_id)] = " "
                    if str(track.track_id) not in check:
                        check[str(track.track_id)] = None

                    #確保不會重複判
                    p_centerimg = show[y_center-1:y_center+1,x_center-1:x_center+1]
                    if (p_centerimg == [255, 255, 255]).all():
                        if ("down" in dir_locate[str(track.track_id)]):
                            if check[str(track.track_id)] is not True:
                                check[str(track.track_id)] = True
                                enter += 1
                        elif ("up" in dir_locate[str(track.track_id)]):
                            if check[str(track.track_id)] is not False:
                                check[str(track.track_id)] = False
                                if enter > 0:
                                    enter -= 1
                                    leave += 1

                    # #add moveline
                    dir_n[str(track.track_id)].append((x_center,y_center))
                    # for  ii in np.arange(1, len(dir_n[str(track.track_id)])):
                    #     i = len(dir_n[str(track.track_id)]) - ii
                    #     thickness = int(np.sqrt(5/(float(ii + 1))) * 3.2)
                    #     cv2.line(show, dir_n[str(track.track_id)][i - 1], dir_n[str(track.track_id)][i], (0, 250, 253), thickness)
                    # cv2.circle(show, (x_center,y_center), 3, (0,0,225), -1)
                    #每8幀判斷方位
                    if len(dir_n[str(track.track_id)]) == 4:
                        if dir_n[str(track.track_id)][0][0]-x_center > 5:
                            dir_t ="left"
                        elif dir_n[str(track.track_id)][0][0]-x_center < -5:
                            dir_t ="right"
                        else:
                            dir_t =" "
                        if dir_n[str(track.track_id)][0][1]-y_center > 5 :
                            dir_y ="up"
                        elif dir_n[str(track.track_id)][0][1]-y_center < -5:
                            dir_y ="down"
                        else:
                            dir_y =" "
                        dir_locate[str(track.track_id)] = dir_t+" "+dir_y 
                        del dir_n[str(track.track_id)]

                    # cv2.putText(show,"ID:%s "%(str(track.track_id))+"dir: %s"%(dir_locate[str(track.track_id)]), (int(bbox[0]), int(bbox[1])+5),cv2.FONT_HERSHEY_COMPLEX_SMALL, 2, (255, 255, 100), 2)
                    cv2.rectangle(frame, (int(bbox[0]), int(bbox[1])), (int(bbox[2]), int(bbox[3])),
                                        (int(self.c[track.track_id % 32, 0]),
                                        int(self.c[track.track_id % 32, 1]),
                                        int(self.c[track.track_id % 32, 2])), -1)

                overlapping = cv2.addWeighted(frame, 0.4, show, 0.6, 0)
                overlapping = cv2.resize(overlapping, (640, 360), interpolation=cv2.INTER_CUBIC)
                background[120:480,0:640] = overlapping
                cv2.putText(background, "{0:^5s}".format(format(enter,",")), (60,780),cv2.FONT_HERSHEY_DUPLEX,2, (255, 255, 255), 2, cv2.LINE_AA)
                cv2.putText(background, "{0:^5s}".format(format(leave,",")), (380,780),cv2.FONT_HERSHEY_DUPLEX,2, (255, 255, 255), 2, cv2.LINE_AA)
                cv2.putText(background, time.strftime('%Y-%m-%d %I:%M:%S %p', time.localtime()), (180,935), cv2.FONT_HERSHEY_DUPLEX,1, (255, 255, 255), 1, cv2.LINE_AA)
                # fps  = (fps + (1./(time.time()-t1))) / 2
                # cv2.putText(background, "fps= %.2f"%(fps), (0, 40),cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 1)
                s2 = datetime.datetime.now().second
                if s2 - s1 == 1:
                  self.push_nodered((self.cam_frame,overlapping,background))
                s1 = s2
                s4 = datetime.datetime.now().minute
                if abs(s4 - s3) == 10:
                    with open("p_ount_data.txt", 'w') as f:
                        f.write("{0},{1},".format(enter,leave))
                s3 = s4
                cv2.imshow(out_win,background)
                # cv2.imshow("123",P_frame)
            key= cv2.waitKey(1) & 0xff

def main():
    pc = People_counting()
    pc.loop_and_detect(conf_th=0.3)
    exit()
if __name__ == '__main__':
    main()
