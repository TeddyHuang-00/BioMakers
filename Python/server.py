# Python内置包
import base64
import os
import socket
import time
from calendar import timegm
from datetime import datetime, timedelta

# 外部包
import cv2 as cv
import numpy as np
import streamlit as slt
import tzlocal as tz
from skimage.metrics import structural_similarity as ssim

# 设置页面标题，图标以及显示方式
slt.set_page_config(
    page_title="Remote camera capture powered by Streamlit",
    page_icon="📷",
    layout="centered",
)

# 统计保存在本地的图像时间戳范围（按每小时分割）
@slt.cache
def imageTimeStampsStat(imgList):
    timeStampsCount = {}
    for imgFileName in imgList:
        tt = datetime.fromtimestamp(
            int(imgFileName.split("/")[-1].split(".")[0]), tz.get_localzone()
        )
        # 将时间戳截至所在小时时间段的起始
        tt = tt - timedelta(
            minutes=tt.minute, seconds=tt.second, microseconds=tt.microsecond
        )
        timeStampsCount[tt] = timeStampsCount.get(tt, 0) + 1
    return timeStampsCount


# 设定时间的显示格式
def timeStrFormat(dt):
    return f"{dt.year%100}-{dt.month}-{dt.day}:{dt.hour:>02d}"


# 图像自动白平衡
# 改自 https://stackoverflow.com/questions/46390779/automatic-white-balancing-with-grayworld-assumption/46391574
def whiteBalance(img):
    # 转换为 LAB 色域，比 RGB 更适合做白平衡，详见上面链接
    result = cv.cvtColor(img, cv.COLOR_BGR2LAB)
    result[:, :, 1] = result[:, :, 1] - (
        (np.average(result[:, :, 1]) - 128) * (result[:, :, 0] / 255.0) * 1.1
    )
    result[:, :, 2] = result[:, :, 2] - (
        (np.average(result[:, :, 2]) - 128) * (result[:, :, 0] / 255.0) * 1.1
    )
    return cv.cvtColor(result, cv.COLOR_LAB2BGR)


# 为图像生成可下载的链接
def generateDownloadLink(jpegFile, name):
    with open(jpegFile, "rb") as fin:
        b64content = base64.b64encode(fin.read()).decode()
    return f'<a href="data:file/jpeg;base64,{b64content}" download="{name}.jpg"><input type="button" value="Download"></a>'


# 页面标题
slt.title("A simple interface to remote camera")
# 功能选择（侧边栏）
whatToDo = slt.sidebar.selectbox(
    label="Capture or preview?",
    options=["Manual capture mode", "Show what we got", "Continuous capture mode"],
    index=1,
    help="New functions are on the way",
)

# 最大的 try-catch 捕获任何有可能出现的bug
# 防止报错信息暴露给前端用户
try:
    # 展示已拍照片
    if whatToDo == "Show what we got":
        # 按时间戳排序图片
        imgFileList = sorted(os.listdir("img"))
        # 获取时间戳分段
        tsCount = imageTimeStampsStat(imgFileList)
        # 用户选择起止时间点
        startDate, endDate = slt.select_slider(
            label="Pick a time range",
            options=list(tsCount.keys()),
            value=(list(tsCount.keys())[-2], list(tsCount.keys())[-1]),
            format_func=timeStrFormat,
            help="Only images taken during the time range will be displayed",
        )
        # 由于选取的是每个小时的起始，故所选结束时间节点需要加一小时
        endDate += timedelta(hours=1)
        # 根据所选实践筛选图片文件
        imgFileList = [
            imgFileName
            for imgFileName in imgFileList
            if startDate
            < datetime.fromtimestamp(int(imgFileName.split(".")[0]), tz.get_localzone())
            < endDate
        ]
        # 用户选择时间段内特定文件
        fileName = slt.selectbox(
            label="Select a images to preview in web", options=imgFileList
        )
        # 显示图片
        slt.image(
            image=f"img/{fileName}",
            caption=datetime.fromtimestamp(
                int(fileName.split(".")[0]), tz.get_localzone()
            ),
            use_column_width=True,
        )
        # 刷新按钮和下载按钮分栏
        colLeft, colRight = slt.beta_columns(2)
        with colLeft:
            slt.button(
                label="Refresh",
                help="Newly captured images might not show, cick the button to refresh the page",
            )
        with colRight:
            slt.markdown(
                generateDownloadLink(
                    f"img/{fileName}",
                    str(
                        datetime.fromtimestamp(
                            int(fileName.split(".")[0]), tz.get_localzone()
                        )
                    ),
                ),
                unsafe_allow_html=True,
            )

    # 手动拍摄
    elif whatToDo == "Manual capture mode":
        # 用户选择拍摄 1-10 张数
        numToCapture = slt.slider(
            label="Select number of images to capture",
            min_value=1,
            max_value=10,
            value=1,
            step=1,
            help="Images are taken every ~5s",
        )

        # 三个 empty 占位，用于显示信息
        infoBar = slt.empty()
        status = slt.empty()
        imgContainer = slt.empty()
        # 等待任务
        infoBar.warning("Pending jobs...")
        # 开始按钮
        while not slt.button(
            label="Start", help="Press this button to start your capture!"
        ):
            slt.stop()

        # 尝试将服务器端口绑定至套接字
        try:
            sock = socket.socket()
            # 不指定特定监听 IP（由于ESP32没有公网IP，故为单向套接字）
            host = "0.0.0.0"
            # 指定绑定的服务器端口 80
            port = 80
            sock.bind((host, port))
            # 无限制监听时间，直至手动终止
            sock.listen(0)
        # 如果绑定不成功，一般情况为端口已被占用
        except Exception:
            slt.exception(
                UnboundLocalError("Socket port in use, please try again later")
            )
            if slt.button("Refresh the page"):
                # 很大可能是上一次开启页面使用的端口未被释放
                # 故导致提示端口被占用的错误
                # 一般来源于快速重新加载页面或者多个用户占用同一个端口
                try:
                    # 所以这一行代码大概率不会成功执行
                    # 不过保险起见还是加载了这儿
                    sock.close()
                except Exception:
                    pass
                slt.experimental_rerun()
            slt.stop()

        # 还未到设定的拍摄张数时
        while numToCapture > 0:
            # 打印剩余张数信息
            infoBar.info(f"{numToCapture} shots left")

            # 接受来自 ESP32 的套接字
            client, address = sock.accept()
            # 接收的数据
            content = b""
            # 缓冲分段数（只用来打印一个文字缓冲动画）
            loopNum = 0
            with slt.spinner("Receiving data..."):
                while True:
                    # 接受套接字传输的数据，此处 inAddress 并不会接收到 ESP32 的 IP
                    # 可能是 BUG，但是也无伤大雅，就留在这儿了
                    # 此处 64 指定缓冲页大小，可以视网络情况而定适当调大（这里应该是偏小了）
                    incoming, inAddress = client.recvfrom(64)
                    # 直至无新接收的数据，停止循环
                    if len(incoming) == 0:
                        break
                    else:
                        # 打印接收到的数据大小信息
                        status.info(
                            f"Received content length: {len(content)} from {inAddress}"
                        )
                        loopNum = (loopNum + 1) % 4
                        # 整合到一次完整接收的数据之中
                        content += incoming

            # 如果接收到了来自 ESP32 的数据
            if len(content):
                # 待捕获张数减一
                numToCapture -= 1
                # 记录时间戳（会和实际拍摄时间有秒级的误差）
                timeStamp = timegm(time.gmtime())
                # 放个气球庆祝
                slt.balloons()
                # 将数据写入文件夹 img 之下的临时文件（需要预先建好此文件夹）
                with open(f"img/{timeStamp}-temp.jpg", "wb") as fout:
                    fout.write(content)
                # 保存文件后对图像进行后处理
                rawImg = cv.imread(f"img/{timeStamp}-temp.jpg")
                # 将白平衡后的图像重新写入该文件
                # TODO：自动曝光调整，以及其他图像处理
                cv.imwrite(f"img/{timeStamp}.jpg", whiteBalance(rawImg))
                # 删除临时文件
                os.remove(f"img/{timeStamp}-temp.jpg")
                # 打印成功信息
                status.success(f"Saved to img {timeStamp}.jpg successfully!")
                # 展示捕获的图片
                imgContainer.image(
                    image=f"img/{timeStamp}.jpg",
                    caption=datetime.fromtimestamp(timeStamp, tz.get_localzone()),
                    use_column_width=True,
                )

        # 完成所有任务后关闭套接字
        sock.close()
        # 打印成功完成任务的信息
        infoBar.success(f"Succeddfully taken photos! Go check them out now!")

    # 自动连续拍摄
    elif whatToDo == "Continuous capture mode":
        # 三档 SSIM 数值阈值，用于比较图像差异
        valueMap = {"Low": 0.9, "Medium": 0.95, "High": 0.975}
        # 用户选择差异的敏感度
        # 自我感觉 Low 档正好
        sensitivityLvl = slt.select_slider(
            "Set sensitivity for capture",
            options=["Low", "Medium", "High"],
            value="Low",
            help="The lower sensitivity means fewer captures are taken and only when the image shows great difference",
        )
        sensitivityThreshold = valueMap[sensitivityLvl]

        # 三个 empty 占位，用于显示信息
        infoBar = slt.empty()
        btnContainer = slt.empty()
        imgContainer = slt.empty()

        # 记录用户是否按下终止键
        notGonnaStop = True
        # 终止按钮和开始按钮分栏
        btnLeft, btnRight = slt.beta_columns(2)
        with btnRight:
            if slt.button("Stop"):
                notGonnaStop = False
        with btnLeft:
            if not slt.button("Start"):
                slt.stop()

        # 尝试将服务器端口绑定至套接字，同上
        try:
            sock = socket.socket()
            host = "0.0.0.0"
            port = 80
            sock.bind((host, port))
            sock.listen(0)
        except Exception:
            slt.exception(
                UnboundLocalError("Socket port in use, please try again later")
            )
            if slt.button("Refresh the page"):
                try:
                    sock.close()
                except Exception:
                    pass
                slt.experimental_rerun()
            slt.stop()

        # 如果用户未按终止
        while notGonnaStop:
            # 接收数据同上
            client, address = sock.accept()
            content = b""
            loopNum = 0
            with slt.spinner("Receiving data..."):
                while True:
                    incoming, inAddress = client.recvfrom(64)
                    if len(incoming) == 0:
                        break
                    else:
                        loopNum = (loopNum + 1) % 4
                        content += incoming

            # 如果接收到了数据，别的同上
            if len(content):
                timeStamp = timegm(time.gmtime())
                with open(f"img/{timeStamp}-temp.jpg", "wb") as fout:
                    fout.write(content)
                rawImg = cv.imread(f"img/{timeStamp}-temp.jpg")
                cv.imwrite(f"img/{timeStamp}.jpg", whiteBalance(rawImg))
                os.remove(f"img/{timeStamp}-temp.jpg")

                # 获取以及捕获得所有照片
                imgFileList = sorted(os.listdir("img"))
                # 获取刚获取的图像和上一张图像用于比对
                lastImg, newImg = [
                    cv.imread(os.path.join("img", imgFileName))
                    for imgFileName in imgFileList[
                        len(imgFileList) - 2 : len(imgFileList)
                    ]
                ]
                # 计算两张图像的 SSIM（得分越低差异越大）
                # https://www.pyimagesearch.com/2017/06/19/image-difference-with-opencv-and-python/
                SSIMscore = float(
                    ssim(
                        cv.cvtColor(lastImg, cv.COLOR_BGR2GRAY),
                        cv.cvtColor(newImg, cv.COLOR_BGR2GRAY),
                    )
                )
                # 如果差异程度在阈值之下（即无显著差异）
                if SSIMscore > sensitivityThreshold:
                    # 删除重复图片
                    os.remove(f"img/{timeStamp}.jpg")
                    # 显示删除重复图像的信息
                    infoBar.info(f"Removing similar image from {inAddress}")
                else:
                    # 显示成功捕获新内容的信息
                    infoBar.success(
                        f"Successfully received new image from {inAddress}!"
                    )
                    # 展示新捕获的图片
                    imgContainer.image(
                        image=f"img/{timeStamp}.jpg",
                        caption=f"{datetime.fromtimestamp(timeStamp, tz.get_localzone())} SSIM:{SSIMscore}",
                        use_column_width=True,
                    )

except Exception as e:
    slt.error("Sorry, something went wrong")
    # 出现 bug 需要调试主体功能的时候取消下行注释
    # slt.exception(e)
    if slt.button("Try refresh the page"):
        slt.experimental_rerun()
