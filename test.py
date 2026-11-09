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


# ========== 发送矩形上方左右两角坐标 ==========
def send_grid_coords(ordered):
    tl = ordered[0]
    tr = ordered[1]
    msg = "{},{},{},{}\n".format(int(tl[0]), int(tl[1]), int(tr[0]), int(tr[1]))
    ser.write(msg.encode())


# ========== 发送棋盘状态(持续) ==========
def send_board_state(state):
    msg = ",".join(state) + "\n"
    ser.write(msg.encode())


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
        upper_black = np.array([180, 80, 75])
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
        lower_white = np.array([0, 0, 190])
        upper_white = np.array([180, 60, 255])
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
        print("[STATE]", ",".join(prev_board_state))
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
        print("[STATE]", ",".join(prev_board_state))
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
    print("[STATE]", ",".join(current_state))

    # 坐标发送阶段
    if send_coord:
        send_grid_coords(ordered)
        print("[COORDS]", "{},{},{},{}".format(int(ordered[0][0]), int(ordered[0][1]), int(ordered[1][0]), int(ordered[1][1])))
        img.draw_string(8, 8, "sending coords...", image.COLOR_YELLOW, scale=1)
        tl_x, tl_y = int(ordered[0][0]), int(ordered[0][1])
        tr_x, tr_y = int(ordered[1][0]), int(ordered[1][1])
        img.draw_circle(tl_x, tl_y, 5, image.COLOR_YELLOW, thickness=-1)
        img.draw_circle(tr_x, tr_y, 5, image.COLOR_YELLOW, thickness=-1)
        img.draw_string(tl_x, tl_y - 12, "TL", image.COLOR_YELLOW, scale=1)
        img.draw_string(tr_x, tr_y - 12, "TR", image.COLOR_YELLOW, scale=1)
        if time.ticks_diff(now, coord_send_start) >= COORD_SEND_DURATION:
            send_coord = False
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
