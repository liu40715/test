k3s 筆記
===
叢集服務系統基礎架構
![](http://10.88.26.157:8080/codimd/uploads/upload_75f187a93db4396939fc85f9869dd1c4.png)
## OS 網路環境調整
參考 https://ithelp.ithome.com.tw/articles/10223290
* 設備 IP 查詢
    ```
    ifconfig
    ```
* 查詢 設備名稱
    ```
    cat /etc/hostname
    ```
* 增加識別項目
    ```
    nano /etc/hosts
    #添加項目
    10.88.33.47  cimnb101
    ```
## 調整DNS解析Server
* 修改 OS 中的解析設定檔
    ```
    nano /etc/resolv.conf
    ```
* 修改 nameserver 項目後方 IP
    ```
    nameserver 8.8.8.8
    ```
## K3s server、agent端安裝
* k3s server安裝指令(需外網)
    * INSTALL_K3S_VERSION: 指定安裝 K3s 的版本
    * INSTALL_K3S_EXEC: 指定 k3s server 執行的 option
        --docker: 選用 Docker 當作 K3s 的 container 引擎 
    ```
    export K3S_NODE_NAME=master
    export K3S_EXTERNAL_IP=${IPADDR}
    export INSTALL_K3S_EXEC="--docker --node-ip=$K3S_EXTERNAL_IP --node-external-ip=$K3S_EXTERNAL_IP"
    curl -sfL https://get.k3s.io | sh -
    ```
* 取得server token(建立agent節點用)
    ```
    sudo cat /var/lib/rancher/k3s/server/node-token
    ```
* k3s worker節點安裝指令(需外網)
    ```
    export K3S_URL="https://${K3SMASTER_IPADDRESS}:6443"
    export K3S_TOKEN="${NODE_TOKEN}"
    export K3S_NODE_NAME=worker
    export INSTALL_K3S_EXEC="--docker"
    curl -sfL https://get.k3s.io | sh -
    ```
#### Node節點ROLES設定
K3s在指派Node節點後查看Node會發現ROLES除了master，其他節點都顯示為none

![](http://10.88.26.157:8080/codimd/uploads/upload_aebc5d015588bdb66cbc4a150b696221.png)

可以透過手動方式設定 ROLES
```
kubectl label nodes <your_node> kubernetes.io/role=<your_new_label>
//例如
kubectl label nodes k3s-node1 kubernetes.io/role=worker
```
設定後，查看就會顯示 worker
![](http://10.88.26.157:8080/codimd/uploads/upload_daf57ffec41443793f81d9321a6f6b45.png)
## K3s server、agent端離線安裝
k3s Github 參考網址：https://github.com/rancher/k3s/releases
k3s 安裝腳本: https://get.k3s.io/
1. Github下載 k3s-airgap-images-arm64.tar 和 k3s-arm64 將文件複製到指定目錄內
    ```
    ##將 K3s 安裝指令碼和 K3s 二進位制檔案移動到對應目錄並授予可執行許可權
    sudo cp k3s-arm64 /usr/local/bin/k3s
    sudo chmod +x /usr/local/bin/k3s
    ##匯入映象到 docker 映象列表
    sudo mkdir -p /var/lib/rancher/k3s/agent/images/
    sudo cp ./k3s-airgap-images-arm64.tar     /var/lib/rancher/k3s/agent/images/
    sudo docker load -i /var/lib/rancher/k3s/agent/images/k3s-airgap-images-arm64.tar
    ```
    
    權限調整
    ```
    chmod 755 /usr/bin/k3s
    ```
2. 創建一個install.sh檔將安裝腳本複製到裡面
    ```
    touch install.sh
    #將https://get.k3s.io/裡資料複製貼上
    vi install.sh
    ```
3. 建立一個master利用 install.sh 將安裝腳本複製執行
    ```
    K3S_NODE_NAME=master1 INSTALL_K3S_SKIP_DOWNLOAD=true     INSTALL_K3S_EXEC="--docker --node-ip=${IPADDR} --node-    external-ip=${IPADDR}" sh install.sh
    ```
    
    成功建立master結果
![](http://10.88.26.157:8080/codimd/uploads/upload_16aaceb0b2f07c42f527cd55e06247c1.png)

4. 輸入指令確認k3s master是否建立成功
    ```
    sudo k3s kubectl get node -o wide
    ```
    ![](http://10.88.26.157:8080/codimd/uploads/upload_7414a03cfc261e08f0c19489eb7933f4.png)

5. 建立Agent
    ```
    INSTALL_K3S_SKIP_DOWNLOAD=true INSTALL_K3S_EXEC="--    docker" K3S_NODE_NAME=worker1 K3S_URL=https://${master_IPADDR}:6443  K3S_TOKEN=${token} sh install.sh 
    ````

    成功建立Agent結果
![](http://10.88.26.157:8080/codimd/uploads/upload_7cafc9706ecb99d22235bce811baadac.png)

6. 輸入指令確認k3s agent是否建立成功
    ```
    sudo k3s kubectl get node -o wide
    ```
    
    ![](http://10.88.26.157:8080/codimd/uploads/upload_a63c6d653182efb46dfcc3fb94c14024.png)
## K3s server、agent端離線安裝(公司內部)
* 安裝server 
    1. 先loadimage
    ```
    ##cd /app/k3s
    root@cimnb101:/app/k3s# docker load -i nginx-image.tar
    root@cimnb101:/app/k3s# docker load -i  rancher_rancher_v2.3.3_amd64.tar
    ```
    2. 安裝server指令
    ```
    curl -sfL http://10.88.33.47:8081 | sh -s - \
  --docker \
  --kube-apiserver-arg feature-gates="TTLAfterFinished=true" \
  --kube-scheduler-arg feature-gates="TTLAfterFinished=true" \
  --kube-controller-manager-arg feature-gates="TTLAfterFinished=true" \
  --kube-cloud-controller-manager-arg feature-gates="TTLAfterFinished=true" \
  --kubelet-arg feature-gates="TTLAfterFinished=true" \
  --kube-proxy-arg feature-gates="TTLAfterFinished=true" \
  --disable-network-policy
    ```
    3. agent端指令

    ```
    curl -sfL http://10.88.33.47:8081 | \
   K3S_URL=https://10.88.33.47:6443 \
       K3S_TOKEN=K10748a7ea6b9d8f7989ce6ba8dbd7c21e2a62f5e6e8dc7f41da53858b693f2caab::server:1a195bd88a54f5247ab4765a1cbdff34 \
   sh -s - \
  --docker \
  --kubelet-arg feature-gates="TTLAfterFinished=true" \
  --kube-proxy-arg feature-gates="TTLAfterFinished=true" \
  ```
    4. 查看是否安裝成功
    ```
    root@cimnb101:/app/k3s/nginx# tail -f /var/log/syslog
    root@cimnb101:/app/k3s/nginx# sudo k3s kubectl get nodes
    ```
    5. 將rancher的docker拉起來
    ```
    root@cimnb101:/app/k3s# ./nginx.sh
    #docker run --restart=always -d -p 8081:80 --name=nginx-8081 -v /app/k3s/nginx.conf:/etc/nginx/conf.d/default.conf -v /app/k3s/nginx:/usr/share/nginx/html:ro nginx
    root@cimnb101:/app/k3s# ./rancher.sh
    #docker run -d --restart=unless-stopped -p 8000:80 -p 8443:443 -v /app/rancher/rancher:/var/lib/rancher rancher/rancher:v2.3.3
    root@cimnb101:/app# docker ps    #確認是否成啟動docker
    ```
    6. 到網頁去複製 rancher叢集增加指令  https://10.88.33.47:8443/
        rancher 帳密從拓譜圖查詢 http://10.88.26.80/edge/
        登入空白處輸入:login 
        密碼:cim$web
        
        登出輸入:loginout
        第一次登入currently password:admin
        new password:cim$ltk8s
    7. 增加叢集
    https://10.88.33.47:8443/  (global->add cluster)
![](http://10.88.26.157:8080/codimd/uploads/upload_8c2e7db931e54c26eb4ef3823031e5e5.png)
![](http://10.88.26.157:8080/codimd/uploads/upload_c78e75555f3dd8f9d09baf61e68f893f.png)
![](http://10.88.26.157:8080/codimd/uploads/upload_33fd75557ddb113f82c2ca31ca8a3843.png)

![](http://10.88.26.157:8080/codimd/uploads/upload_9711aeea0de5bccdf6ffed7bb9097941.png)

複製圖中反白那段指令(注意:在指令中kubectl前需加上k3s)    
```
curl --insecure -sfL https://10.88.33.47:8443/v3/import/b6k8sdmc5wsvtq59kw9xw    jcsmdqmnhfv6ddj2hrzpmbcpftjwlvh2s.yaml | k3s kubectl apply -f -
```
    
8. 測試POD派送
    ```
    root@cimnb101:/app/danny# sudo k3s kubectl create -f test.yaml
    root@cimnb101:/app/danny# docker logs 3912e771bcc3
    root@cimnb101:/app/danny# sudo k3s kubectl delete -f test.yaml    
    ```
    ![](http://10.88.26.157:8080/codimd/uploads/upload_555dd7774b2517b7440b0ac72cc74a95.png)
    ![](http://10.88.26.157:8080/codimd/uploads/upload_8c346454cd4b33bbd3de7160bfe2eacb.png)
    ![](http://10.88.26.157:8080/codimd/uploads/upload_dd35e5f083f18adbdb1e294ea8922176.png)
    
    ![](http://10.88.26.157:8080/codimd/uploads/upload_b1f00b0cce62ca75988a7b0a12bcaf84.png)

## K3s server、agent端解除安裝
參考 https://ithelp.ithome.com.tw/articles/10224167
* k3s Server、Agent 應用程式內容清除指令
    * 線上版
    ```
    curl -sfL https://get.k3s.io | k3s-killall.sh
    ```
    * 離線版
    ```
    /usr/local/bin/k3s-killall.sh
    ```
* k3s Server 應用程式解除安裝指令
    * 線上版
    ```
    curl -sfL https://get.k3s.io | k3s-uninstall.sh
    ```
    * 離線版
    ```
    /usr/local/bin/k3s-uninstall.sh
    ```

* k3s Agent 應用程式解除安裝指令
    * 線上版 
    ```
    curl -sfL https://get.k3s.io | k3s-agent-uninstall.sh
    ```
    * 離線版
    ```
    /usr/local/bin/k3s-agent-uninstall.sh
    ```
* docker檔案刪除
    * 全部contanier刪除
    ```
    docker rm -f $(docker ps -a -q)
    ```
## K3s基礎指令
參考 https://ithelp.ithome.com.tw/articles/10224539
* Node
  ```
  k3s kubectl get node #簡易檢查
  k3s kubectl delete node #刪除節點
  k3s kubectl get node -o wide #進階檢查
  k3s kubectl describe node #檢視全部 Node
  k3s kubectl describe node ${Node-Name} #檢視指定 Node
  k3s kubectl create -f ${pod-file} #派送指令
  ```
* Pod
    ```
    k3s kubectl create -f ${pod-file} #建立POD
    k3s kubectl get pod #簡易檢查
    k3s kubectl get pod -o wide #進階檢查
    k3s kubectl describe pod #檢視全部POD
    k3s kubectl describe pod ${Pod-Name} #檢視指定POD
   ```

* Pod Backend 設定
    ```
    k3s kubectl exec -ti ${pod-name} bash #操作指令
    k3s kubectl delete pod ${pod-name} #操作指令
    k3s kubectl delete pod ${pod-name} --grace-period=0 --force #操作指令
    ```
* Container / Pod 狀態指令 (crictl)
    *  這邊是獨立在 Agent 端自身的 Containerd 使用，所有的 刪除 及       停止 Pod / Container 皆會因為 k3s 叢集監控而重新啟動
    ```
    k3s crictl images #檢視 Image
    k3s crictl pull ${Image-Name} #下載 Image
    k3s crictl rmi ${Image-Id} #刪除 Image
    k3s crictl ps #檢視 Container
    k3s crictl inspect ${container-id} #特定 Pod 的配置訊息
    k3s crictl stats -id ${pod-id} #指定 Container
    k3s crictl stop ${container-id} #停止 Container
    k3s crictl pods #所有執行中的 Pod
    k3s crictl inspectp ${pod-id} #特定 Pod 的配置訊息
    k3s crictl stats -p ${pod-id} #Pod 消耗系統資源狀態
    k3s crictl stopp ${pod-id} #停止 Pod
    k3s crictl rmp ${pod-id} #刪除 Pod
    ```
## k3s POD 介紹
參考:https://ithelp.ithome.com.tw/articles/10235432
* POD 特性
    1. 包含多個 container
    2. 同一 POD 中的 container 可以直接以 127.0.0.1 的方式，互相溝通。
    3. 同一個 POD 中的 container 共享那個 POD 的 volume
    4. 同一個 POD 中的 container 是同時被調度 (因為 k8s 最小部署單位是 POD 不是 container)

* yaml 檔案設計
    * 建立 POD
    ```
    apiVersion: v1
    kind: Pod
    metadata:
      name: test
    spec:
      containers:
      - name: test
        image: python:3.7.12-slim
        imagePullPolicy: cimnb101
        command: ["/bin/sh", "-c", "while true; do echo hello; sleep 60; done"]
        nodeSelector:
          k3s.io/hostname: cimnb101
    ```
    * 建立 Deployment 
    ```
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: test-deployment
      labels:
        app: test
    spec:
      replicas: 1
      selector:
        matchLabels:
          app: test
      template:
        metadata:
          labels:
            app: test
        spec:
          containers:
          - name: test
            image: ubuntu:18.04
            command: ["/bin/sh", "-c", "while true; do echo hello; sleep 60; done"]
          nodeSelector:
            k3s.io/hostname: adlink-desktop
    ```
    * flask架站
    ```
    apiVersion: v1
    kind: Service
    metadata:
      name:flask-service
    spec:
      selector:
        app: flask-python
      ports:
      - protocol: "TCP"
        port: 8000
        targetPort: 80
      type: LoadBalancer

    ---
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: flask-python
    spec:
      selector:
        matchLabels:
          app: flask-python
      replicas: 1
      template:
        metadata:
          labels:
            app: flask-python
        spec:
          volumes:
          - name: data
            hostPath:
              path: /app/danny/flask/data
          containers:
          - name: flask-python
            image: flask-mongo:latest
            volumeMounts:
            - name: data
              mountPath: /app
            command: ["/bin/sh", "-c", "while true; do echo hello; sleep 60; done"]
            imagePullPolicy: Never
            ports:
            - containerPort: 80 
    ```
## K3s 叢集Yaml檔案編寫
1. Pod
    一個 Pod 裡面可以有一個或是多個 Container，但一般情況一個 Pod 最好只有一個 Container![]
2.  Service
	Service 就是 Kubernetes 中用來定義「一群 Pod 要如何被連線及存取」的元件。
3.  Deployment
	今天當我們同時要把一個 Pod 做橫向擴展，也就是複製多個相同的 Pod 在 Cluster 中同時提供服務。
4.  ingress
	使用 Ingress ，我們只需開放一個對外的 port number，Ingress 可以在設定檔中設置不同的路徑，決定要將使用者的請求傳送到哪個 Service 物件

    ![](http://10.88.26.157:8080/codimd/uploads/upload_00e48ed7f5f322ecef53b4b3c9d136d6.png)


 


