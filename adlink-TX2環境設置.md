adlink-TX2環境設置
===
## 桌面模式
將桌面模式關掉減少記憶體使用量
(使用free -h來查看)

```
systemctl set-default multi-user.target
```

記憶體占用率980M -> 226M
![](http://10.88.26.157:8080/codimd/uploads/upload_1f34c0394aeada01f6dfea23065a9aa8.png)

* 如果需要開啟
```
systemctl start gdm3.service 
```
## 環境設定與安裝套件
Upgrade all installed packages
* 先將apt套件更新
```
apt update && apt upgrade && apt dist-upgrade && apt autoremove
```
* 安裝套件(主要都是安裝藍芽相關套件)
```
apt install curl python3-pip bluetooth libbluetooth-dev
pip3 install -U pip jetson-stats pybluez pexpect
```
* 在將要執行 Docker 的使用者加入至docker群組內
    * 可以先用groups指令去查有沒有docker,如果沒有輸入下面指令
```
adlink@adlink-desktop:~$ groups
adlink adm cdrom sudo audio dip video plugdev i2c lpadmin gdm sambashare weston-launch gpio
```
```
sudo usermod -aG docker $USER
##執行行完上述指令之後，記得 **重新登入**，再次查看
```
```
adlink@adlink-desktop:~$ groups
adlink adm cdrom sudo audio dip video plugdev i2c lpadmin gdm docker sambashare weston-launch gpio jetson_stats
````
* Add Harbor into docker registry
    * 如果要從habor中Pull images必須在daemon.json加入下面
    ```
    "insecure-registries" : ["10.88.19.126"],    
    "log-opts": {      
    "max-size": "10m",      
    "max-file": "5“
    ```
```linux=
$ sudo vi /etc/docker/daemon.json
    {    
        "default-runtime": "nvidia",    
        "runtimes": {        
            "nvidia": {            
                "path": "nvidia-container-runtime",
                "runtimeArgs": []
            }    
        },    
        "insecure-registries" : ["10.88.19.126"],
        "log-opts": {
            "max-size": "10m",
            "max-file": "5",
        }
    }
$ sudo systemctl restart docker //(check if available: $ docker info)
```
*Jasper @ 2021/09/14*
- [ ] 如何確認新的 registry 有加入成功 ?
- [x] 如何查看 log ?
```
tail -F /var/log/syslog
```
- [x] log 實體檔案在哪 ?
```
/etc/syslog.conf
```
- [ ] 怎麼測試和確認 log 有在限制的大小並 rolling ?

* 使用Shell實現NTP時間伺服器指定同步
  * 參考  https://note.qidong.name/2020/09/timesyncd/
```
sudo vi /etc/systemd/timesyncd.conf 
    NTP=10.88.15.195 #主要NTP伺服器
    FallbackNTP=10.88.15.175 #備用NTP伺服器

sudo service systemd-timesyncd restart
sudo systemctl restart docker #docker重新啟動
```
*Jasper @ 2021/09/14*
- [x] 如何確認 NTP 有生效 ?
```
$ timedatectl status
               Local time: 二 2020-09-22 20:06:05 CST
           Universal time: 二 2020-09-22 12:06:05 UTC
                 RTC time: 二 2020-09-22 12:06:05
                Time zone: Asia/Shanghai (CST, +0800)
System clock synchronized: yes
              NTP service: active
          RTC in local TZ: no
```
## WiFi auto connect
* 設定所有廠區的WIFI帳密
    * 參考 https://www.raspberrypi.com.tw/2152/setting-up-wifi-with-the-command-line/
```
sudo vi /etc/wpa_supplicant/wpa_supplicant.conf

ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
country=TW

network={
        ssid="L3D"
        psk="WiFi@AUHY"
        key_mgmt=WPA-PSK
}
```
* 設定開機完之後才連接wifi
  * 參考 https://gsyan888.blogspot.com/2013/04/raspberry-pi-wireless-network.html
```
vi /etc/network/interfaces

# interfaces(5) file used by ifup(8) and ifdown(8)
# Include files from /etc/network/interfaces.d:
source-directory /etc/network/interfaces.d

allow-hotplug wlan0
#表示wlan裝置可以熱插撥
iface wlan0 inet dhcp 
#表示如果有WLAN網絡卡wlan0 (就是WIFI網絡卡), 則用dhcp獲得IP地址
wpa-conf /etc/wpa_supplicant/wpa_supplicant.conf 
#無線網路 wpa 認證的相關資訊則wpa_supplicant.conf 來提供。
```
* 設定如果插入網路線關閉WIFI
```
vi /etc/NetworkManager/dispatcher.d/50-wifiOnOff
-------名詞註解-------------------------------------
#$0 是指令碼本身的名字
#$1 狀態發生變化的網路接口
#$2 網路接口狀態更新：up, down, vpn-up, vpn-down
---------------------------------------------------
#!/bin/bash
if [ "$2" == up ] || [ "$2" == down ]; then
  if [ `nmcli dev | grep ethernet | grep $1 |  wc -l` -eq 0 ]; then
   # check if interface is not ethernet
   exit
  fi

  if [ `nmcli c show --active | grep ethernet | wc -l` -ne 0 ]; then
    # ethernet connected
    nmcli radio wifi off
    logger "[$0] ADTDC3: $1 $2, turn wifi off"
  else
    # ethernet disconnected
    nmcli radio wifi on
    logger "[$0] ADTDC3: $1 $2, turn wifi on"
  fi
fi
```
*Jasper @ 2021/09/14*
- [ ] 在開機狀態下插入/拔出網路線的反應 ?
- [ ] 在開機狀態下插入網路線，關機，拔掉網路線，開機，會如何?
- [ ] 在開機狀態下拔掉網路線，關機，插入網路線，開機，會如何?

## Others
* 刪除USER root權限
```
deluser cimadmin sudo
```
*Jasper @ 2021/09/14*
- [ ] 如何檢查有生效 ?

* 查看與編輯 crontab
https://blog.gtwang.org/linux/linux-crontab-cron-job-tutorial-and-examples/
```
# 查看自己的 crontab
crontab -l
```
```
# 編輯 crontab 內容
crontab -e
```
```
# 編輯指定使用者的 crontab
crontab -u gtwang -e
```
```
# 刪除 crontab 內容
crontab -r
```
# Docker image 安裝
基本docker指令 http://10.88.26.157/Fw8aU0zuTmykRg-qMmLRkg
## Harbor images 
網址:http://10.88.19.126
帳密:admin/Harbor12345
#### 點一下Pull Command 複製 image name
![](http://10.88.26.157:8080/codimd/uploads/upload_df847f1ef29c0b41259498a6f0c62d58.png)

#### 開啟command視窗
* Harbor images 名稱修改成10.88.19.126如下
```
docker pull 10.88.19.126/probe/tensorflow:1.15.2_keras2.3.1_jetpack4.4-plus
```
* 啟動container
```
docker run -it --rm --runtime=nvidia 10.88.19.126/probe/tensorflow:1.15.2_keras2.3.1_jetpack4.4-plus
```
* 進入container
```
docker exec -it d94f4d105fbc /bin/bash
```
* 實際測試
python執行keras時如果有顯示 physical GPU 代表成功利用GPU來預測
![](http://10.88.26.157:8080/codimd/uploads/upload_1c0ca1c0d0172d621a816ff107fca9fa.png)
Jtop查看
![](http://10.88.26.157:8080/codimd/uploads/upload_d020912de257419ddccbfa2c76e7f3fa.png)


## 根據裝置jetpack下載相對應的docker 
#### Step0：確認你的JetPack SDK版本
```
# jetson_release
```
![](http://10.88.26.157:8080/codimd/uploads/upload_821e7c03b8b3b387d47ebc1117f0ba9f.png)
#### Step1：確認系統預先安裝好的Docker Container
```
#sudo dpkg --get-selections | grep nvidia
```
![](http://10.88.26.157:8080/codimd/uploads/upload_3d45bed10dfe445ffa8d9c4c579a4ada.png)
* adlink 裝置會顯示hold如需解除
```
#sudo apt-mark unhold
```
#### Step2：到nvidia的NGC下載docker(注意版本)
https://ngc.nvidia.com/catalog/containers/nvidia:l4t-tensorflow
```
# sudo docker pull nvcr.io/nvidia/ l4t-tensorflow:r32.5.0-tf1.15-py3
```
#### Step3:執行Docker
##### 注意須加上--runtime nvidia才能吃到host的GPU
```
# sudo docker run -it --rm --runtime nvidia --network host nvcr.io/nvidia/l4t-tensorflow:r32.4.3-tf1.15-py3
```
#### Step4:測試是否成功抓到GPU
```python=
import os
from tensorflow.python.client import device_lib
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "99"
print(device_lib.list_local_devices())
```
![](http://10.88.26.157:8080/codimd/uploads/upload_1fcd1447600158f36b0b43b5c9e5eab6.png)








## edge出廠時必須預先下載的東西 
#### Step1：需要預先載入docker image

* docker pull 10.88.19.126/k3s/edger:tf1.15.2_keras2.3.1_jetpack4.4
* cimadmin@ltoak3s:/app/k3s/nginx
  * k3s-airgap-images-arm64.tar
  * rancher_rancher-agent_v2.3.3_arm64.tar

#### Step2：將需要的檔案搬入edge中
* 在edge中先用su指令獲得權限
```
cimadmin@ltoak3s-an-nano:~$ su
root@ltoak3s-an-nano:/home/cimadmin# cd /root/
```
* 在路徑中創建資料夾
```
mkdir daemon
mkdir daemonLog
```

* 在 cimadmin@ltoak3s-nv-agx:/app/ai365/images/daemon/container/daemon/ 路徑中找到要搬的檔案放入 /root/daemon/
```
cimUtil.sh
daemon/
daemon.sh
scs.conf
scs.sh
```

* 在 cimadmin@ltoak3s-nv-agx:/app/ai365/images/daemon/container/ohters/ 路徑中找到要搬的檔案
```
auto-agent => /usr/local/bin/
bluezutils.py => /usr/local/bin/
wpa_supplicant.conf => /etc/wpa_supplicant/
interfaces => /etc/network/
50-wifiOnOff => /etc/NetworkManager/dispatcher.d/
```

* 先試測搬過來的檔案是否可以成功運行
#### Step3:cronjob設定
這部分我記得試加這兩個其他會自己加入
```
root@ltoak3s-an-nano:~# crontab -e
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

* * * * * cd /root/daemon && ./daemon.sh
0 */3 * * * cd /root/daemon && /bin/sh ./scs.sh > /dev/null 2>&1

```
#### Step4:wifi設定測試
```
可以在裡面加入自己的wifi來測試
root@ltoak3s-an-nano:~/daemon/daemon# cat /etc/wpa_supplicant/wpa_supplicant.conf

```