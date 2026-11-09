# from maix import camera, display, image, app
# import cv2
# import numpy as np

# def find_grid_centers(corners):
#     """
#     corners: List of 4 tuples representing the corners of the 3x3 grid in the order:
#              top-left, top-right, bottom-right, bottom-left
#     """
#     # Define the 3x3 grid points in the normalized coordinate space
#     grid_points = np.array([[0, 0],   [1/3, 0],   [2/3, 0],   [1, 0],
#                             [0, 1/3], [1/3, 1/3], [2/3, 1/3], [1, 1/3],
#                             [0, 2/3], [1/3, 2/3], [2/3, 2/3], [1, 2/3],
#                             [0, 1],   [1/3, 1],   [2/3, 1],   [1, 1]])

#     # Convert corners to numpy array
#     dst_points = np.array(corners, dtype=np.float32)

#     # Define source points for the perspective transform
#     src_points = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], dtype=np.float32)

#     # Compute the perspective transform matrix
#     transform_matrix = cv2.getPerspectiveTransform(src_points, dst_points)

#     # Transform grid points to image coordinate space
#     transformed_points = cv2.perspectiveTransform(np.array([grid_points], dtype=np.float32), transform_matrix)[0]

#     # Calculate the center points of the grid cells
#     centers = []
#     for i in range(0, 3):
#         for j in range(0, 3):
#             cx = (transformed_points[i * 4 + j][0] + transformed_points[i * 4 + j + 1][0] +
#                   transformed_points[(i + 1) * 4 + j][0] + transformed_points[(i + 1) * 4 + j + 1][0]) / 4
#             cy = (transformed_points[i * 4 + j][1] + transformed_points[i * 4 + j + 1][1] +
#                   transformed_points[(i + 1) * 4 + j][1] + transformed_points[(i + 1) * 4 + j + 1][1]) / 4
#             centers.append((int(cx), int(cy)))
#     return centers

# def main():
#     disp = display.Display()
#     cam = camera.Camera(320, 240)

#     kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3,3))

#     # 缓存上一帧棋盘状态
#     prev_board_state = None

#     while not app.need_exit():
#         img = cam.read()

#         img_cv = image.image2cv(img, False, False)
#         gray = cv2.cvtColor(img_cv, cv2.COLOR_RGB2GRAY)

#         # 高斯模糊去噪声
#         blurred = cv2.GaussianBlur(gray, (5, 5), 0)

#         # 边缘检测
#         edged = cv2.Canny(blurred, 50, 150)

#         # 膨胀处理
#         dilated = cv2.dilate(edged, kernel, iterations=1)

#         # 腐蚀处理
#         eroded = cv2.erode(dilated, kernel, iterations=1)

#         # 查找轮廓
#         contours, _ = cv2.findContours(eroded, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

#         # 当前帧棋盘状态与中心点坐标
#         current_board_state = ['empty'] * 9
#         current_centers = None  # 新增：保存全部9格中心点坐标
#         chess_list = []

#         if len(contours) > 0:
#             # 筛选出最大的轮廓
#             largest_contour = max(contours, key=cv2.contourArea)

#             # 近似多边形
#             epsilon = 0.02 * cv2.arcLength(largest_contour, True)
#             approx = cv2.approxPolyDP(largest_contour, epsilon, True)

#             # 如果找到的是一个四边形
#             if len(approx) == 4:
#                 corners = approx.reshape((4, 2))

#                 # 按顺序排列角点（左上、右上、右下、左下）
#                 rect = np.zeros((4, 2), dtype="int")
#                 points_sum = corners.sum(axis=1)
#                 rect[0] = corners[np.argmin(points_sum)]
#                 rect[2] = corners[np.argmax(points_sum)]
#                 points_diff = np.diff(corners, axis=1)
#                 rect[1] = corners[np.argmin(points_diff)]
#                 rect[3] = corners[np.argmax(points_diff)]
#                 corners = rect

#                 # 绘制四边轮廓
#                 cv2.drawContours(img_cv, [approx], -1, (0, 255, 0), 2)

#                 # 找出9宫格各个中心点
#                 centers = find_grid_centers(corners)

#                 # 画出中心点，添加编号
#                 if len(centers) == 9:
#                     current_centers = centers  # 保存全部中心点，供打印使用
#                     for i in range(9):
#                         x, y = centers[i][0], centers[i][1]
#                         cv2.circle(img_cv, (x, y), 2, (0, 255, 0), -1)
#                         img = image.cv2image(img_cv, False, False)

#                         img.draw_string(x, y, f"{i + 1}", image.COLOR_WHITE)

#                         # 设定棋子判定区域宽度
#                         width = 20
#                         img.draw_rect(x-width//2, y-width//2, width, width, image.COLOR_WHITE)

#                         # 直方图均衡化 & 获取直方图 & 中位值/均值/众数...
#                         img = img.histeq(adaptive = True)
#                         hist = img.get_histogram(thresholds = [[0, 100, -128, 127, -128, 127]], roi = [x-width//2, y-width//2, width, width])
#                         value = hist.get_statistics().a_median()

#                         # 根据区间值判定棋子颜色
#                         color_chess = ''
#                         #-110
#                         if value < -90:
#                             color_chess = 'black'
#                         #-80
#                         elif value > -60:
#                             color_chess = 'white'

#                         # 更新当前帧格子状态
#                         if color_chess:
#                             current_board_state[i] = color_chess
#                         else:
#                             current_board_state[i] = 'empty'

#                         if color_chess != '':
#                             img.draw_string(x, y+10, color_chess, image.COLOR_WHITE)
#                             chess_list.append({
#                                 "格子编号": i+1,
#                                 "像素坐标X": x,
#                                 "像素坐标Y": y,
#                                 "棋子颜色": color_chess
#                             })
#             else:
#                 # 识别到轮廓但不是四边形，棋盘状态无效
#                 current_board_state = None
#                 current_centers = None
#         else:
#             # 没有轮廓，未识别到棋盘
#             current_board_state = None
#             current_centers = None
#             img.draw_string(8, 8, "no rectangle", image.COLOR_RED, scale=1)

#         # 核心：状态变化才打印，且打印全部9格数据
#         if current_board_state != prev_board_state:
#             # 更新缓存
#             prev_board_state = current_board_state.copy() if current_board_state else None

#             if current_board_state is None:
#                 print("===== 棋盘状态更新 =====")
#                 print("未识别到有效棋盘")
#                 print("=======================")
#             else:
#                 print("===== 棋盘状态更新（全部9格） =====")
#                 for i in range(9):
#                     grid_num = i + 1
#                     state = current_board_state[i]
#                     cx, cy = current_centers[i]
#                     print(f"第{grid_num}格 | 状态：{state:<6} | 坐标：({cx}, {cy})")
#                 print("==================================")

#         disp.show(img)

# if __name__ == '__main__':
#     main()

#九个格子的中心点坐标



from maix import app, camera, display, image, time, uart
import cv2
import numpy as np

# ========== 全局参数配置 ==========
CAM_W = 320
CAM_H = 240
MIN_AREA = 1200
MIN_ASPECT = 0.45
MAX_ASPECT = 2.8
APPROX_EPSILON_RATIO = 0.02
ADAPTIVE_BLOCK_SIZE = 31
ADAPTIVE_C = 8

# 棋子检测参数
PIECE_MIN_R = 8
PIECE_MAX_R = 35
CIRCULARITY_THRESH = 0.35

# 坐标发送持续时间(毫秒)
COORD_SEND_DURATION = 5000

# 串口初始化
ser = uart.UART("/dev/serial0", 115200)

# ========== 状态变量 ==========
prev_board_state = ["0"] * 9
saved_centers = None
saved_ordered = None
coord_send_start = 0
send_coord = True
first_detect = True


# ========== 矩形检测 ==========
def find_best_rectangle(img_cv):
    gray = cv2.cvtColor(img_cv, cv2.COLOR_RGB2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    binary = cv2.adaptiveThreshold(
        blur, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
        cv2.THRESH_BINARY_INV, ADAPTIVE_BLOCK_SIZE, ADAPTIVE_C
    )
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best = None
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < MIN_AREA:
            continue
        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, APPROX_EPSILON_RATIO * perimeter, True)
        if len(approx) != 4:
            continue
        x, y, w, h = cv2.boundingRect(approx)
        if h == 0:
            continue
        aspect = w / h
        if aspect < MIN_ASPECT or aspect > MAX_ASPECT:
            continue
        candidate = {"area": area, "rect": (x, y, w, h), "approx": approx}
        if best is None or area > best["area"]:
            best = candidate
    return best


# ========== 角点排序 ==========
def order_points(points):
    pts = points.reshape(4, 2).astype("float32")
    ordered = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    ordered[0] = pts[np.argmin(s)]
    ordered[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1).reshape(4)
    ordered[1] = pts[np.argmin(diff)]
    ordered[3] = pts[np.argmax(diff)]
    return ordered


# ========== 角点匹配：新角点匹配到参考顺序 ==========
def match_corners(new_pts, ref_pts):
    result = np.zeros_like(ref_pts)
    used = set()
    for i in range(4):
        best_j = -1
        best_dist = float('inf')
        for j in range(4):
            if j in used:
                continue
            d = np.hypot(new_pts[j][0] - ref_pts[i][0], new_pts[j][1] - ref_pts[i][1])
            if d < best_dist:
                best_dist = d
                best_j = j
        result[i] = new_pts[best_j]
        used.add(best_j)
    return result


# ========== 透视变换 ==========
def warp_perspective_target(img_cv, ordered):
    tl, tr, br, bl = ordered
    warp_w = int(max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl)))
    warp_h = int(max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr)))
    if warp_w < 20 or warp_h < 20:
        return None
    dst = np.array([[0, 0], [warp_w - 1, 0], [warp_w - 1, warp_h - 1], [0, warp_h - 1]], dtype="float32")
    matrix = cv2.getPerspectiveTransform(ordered, dst)
    if abs(np.linalg.det(matrix)) < 1e-6:
        return None
    warped = cv2.warpPerspective(img_cv, matrix, (warp_w, warp_h))
    return {"image": warped, "matrix": matrix, "size": (warp_w, warp_h)}


# ========== 绘制矩形框 ==========
def draw_polygon(img, ordered):
    pts = ordered.astype("int32")
    for i in range(4):
        x1, y1 = int(pts[i][0]), int(pts[i][1])
        x2, y2 = int(pts[(i + 1) % 4][0]), int(pts[(i + 1) % 4][1])
        img.draw_line(x1, y1, x2, y2, image.COLOR_GREEN, thickness=2)


# ========== 九宫格中心点计算 ==========
def compute_grid_centers(ordered):
    tl, tr, br, bl = ordered
    centers = []
    for row in range(3):
        for col in range(3):
            t = (col + 0.5) / 3.0
            top_x = tl[0] + (tr[0] - tl[0]) * t
            top_y = tl[1] + (tr[1] - tl[1]) * t
            bot_x = bl[0] + (br[0] - bl[0]) * t
            bot_y = bl[1] + (br[1] - bl[1]) * t
            s = (row + 0.5) / 3.0
            cx = int(top_x + (bot_x - top_x) * s)
            cy = int(top_y + (bot_y - top_y) * s)
            centers.append((cx, cy))
    return centers


# ========== 发送网格坐标 ==========
def send_grid_coords(centers):
    coords = []
    for x, y in centers:
        coords.append(str(x))
        coords.append(str(y))
    msg = ",".join(coords)
    ser.write(("*" + msg + "#").encode())
    print(("*" + msg + "#").encode())

# def send_grid_coords(centers):
#     c1 = centers[0]
#     c9 = centers[8]
#     msg = "*{},{},{},{}#".format(c1[0], c1[1], c9[0], c9[1])
#     ser.write(msg.encode())


# ========== 发送棋盘状态(持续) ==========
def send_board_state(state):
    msg = ",".join(state) + "\n"
    # ser.write(msg.encode())


# ========== 棋子检测：HSV颜色阈值判断 ==========
def detect_pieces(img_cv, centers):
    state = ["0"] * 9
    hsv = cv2.cvtColor(img_cv, cv2.COLOR_RGB2HSV)
    img_h, img_w = hsv.shape[:2]

    for i, (cx, cy) in enumerate(centers):
        cell_r = PIECE_MAX_R + 8
        x1 = max(0, cx - cell_r)
        y1 = max(0, cy - cell_r)
        x2 = min(img_w, cx + cell_r)
        y2 = min(img_h, cy + cell_r)

        roi_hsv = hsv[y1:y2, x1:x2]
        if roi_hsv.size == 0:
            continue

        local_cx = cx - x1
        local_cy = cy - y1

        # 黑棋: V < 75, S < 80
        lower_black = np.array([0, 0, 0])
        upper_black = np.array([180, 100, 95])
        dark_mask = cv2.inRange(roi_hsv, lower_black, upper_black)
        dark_contours, _ = cv2.findContours(dark_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in dark_contours:
            area = cv2.contourArea(cnt)
            if area < 80:
                continue
            (bx, by), br = cv2.minEnclosingCircle(cnt)
            dist = np.hypot(bx - local_cx, by - local_cy)
            if dist < cell_r * 0.5 and br > PIECE_MIN_R and br < PIECE_MAX_R:
                state[i] = "1"
                break

        if state[i] == "1":
            continue

        # 白棋: V > 190, S < 60
        lower_white = np.array([0, 0, 160])
        upper_white = np.array([180, 90, 255])
        white_mask = cv2.inRange(roi_hsv, lower_white, upper_white)
        white_contours, _ = cv2.findContours(white_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in white_contours:
            area = cv2.contourArea(cnt)
            if area < 80:
                continue
            (bx, by), br = cv2.minEnclosingCircle(cnt)
            dist = np.hypot(bx - local_cx, by - local_cy)
            if dist < cell_r * 0.5 and br > PIECE_MIN_R and br < PIECE_MAX_R:
                state[i] = "1"
                break

    return state


# ========== 初始化 ==========
cam = camera.Camera(CAM_W, CAM_H)
disp = display.Display()

# ========== 主循环 ==========
while not app.need_exit():
    img = cam.read()
    img_cv = image.image2cv(img, False, False)

    best = find_best_rectangle(img_cv)

    if not best:
        img.draw_string(8, 8, "no board", image.COLOR_RED, scale=1)
        send_board_state(prev_board_state)
        # print("[STATE]", ",".join(prev_board_state))
        disp.show(img)
        first_detect = True
        continue

    if first_detect:
        ordered = order_points(best["approx"])
        saved_ordered = ordered.copy()
    else:
        new_pts = best["approx"].reshape(4, 2).astype("float32")
        ordered = match_corners(new_pts, saved_ordered)

    warp_result = warp_perspective_target(img_cv, ordered)

    if not warp_result:
        img.draw_string(8, 8, "warp failed", image.COLOR_RED, scale=1)
        send_board_state(prev_board_state)
        # print("[STATE]", ",".join(prev_board_state))
        disp.show(img)
        continue

    draw_polygon(img, ordered)
    centers = compute_grid_centers(ordered)

    # 检测棋盘是否移动(中心点偏移超过15像素)
    board_moved = False
    if saved_centers is not None:
        for i in range(9):
            dx = centers[i][0] - saved_centers[i][0]
            dy = centers[i][1] - saved_centers[i][1]
            if abs(dx) > 15 or abs(dy) > 15:
                board_moved = True
                break

    now = time.ticks_ms()

    if first_detect:
        # 首次检测到棋盘 → 发5秒坐标
        coord_send_start = now
        send_coord = True
        saved_centers = list(centers)
        first_detect = False
    elif board_moved:
        # 坐标变了 → 重新发5秒坐标
        coord_send_start = now
        send_coord = True
        saved_centers = list(centers)

    # 一直检测棋子并发送状态
    current_state = detect_pieces(img_cv, centers)
    prev_board_state = current_state[:]
    send_board_state(current_state)
    # print("[STATE]", ",".join(current_state))

    # 坐标发送阶段
    if send_coord:
        send_grid_coords(centers)
        # print("[COORDS]", ",".join(["{},{}".format(x, y) for x, y in centers]))
        # print("{},{},{},{}\n".format(centers[0][0], centers[0][1], centers[8][0], centers[8][1]))
        img.draw_string(8, 8, "sending coords...", image.COLOR_YELLOW, scale=1)
        for ci, (cx2, cy2) in enumerate(centers):
            img.draw_circle(cx2, cy2, 3, image.COLOR_YELLOW, thickness=-1)
        # if time.ticks_diff(now, coord_send_start) >= COORD_SEND_DURATION:
        #     send_coord = False
    else:
        for ci, (cx2, cy2) in enumerate(centers):
            img.draw_circle(cx2, cy2, 3, image.COLOR_GREEN, thickness=-1)
            if current_state[ci] == "1":
                img.draw_circle(cx2, cy2, 15, image.COLOR_RED, thickness=2)
                img.draw_string(cx2 - 4, cy2 + 8, "1", image.COLOR_RED, scale=1)
            else:
                img.draw_string(cx2 - 4, cy2 + 8, "0", image.COLOR_WHITE, scale=1)

    fps = time.fps()
    if fps > 0:
        img.draw_string(8, img.height() - 20, "fps: {:.1f}".format(fps), image.COLOR_WHITE, scale=1)

    disp.show(img)
