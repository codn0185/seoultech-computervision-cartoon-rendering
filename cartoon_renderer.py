import os
import numpy as np
import cv2 as cv
import tkinter as tk
from tkinter import filedialog


KEYCODE_DICT: dict[str, int] = {
    "enter": 13,
    "esc": 27,
    "space": 32,
}


class CartoonRenderer:
    # 윈도우 제목
    WINDOW_TITLE: str = "Cartoon Renderer"

    # [원본, 필터 1 적용, 필터 2 적용, ...]
    image_list: list[np.ndarray] = []
    image_index: int = 0

    def __init__(self):
        image_file_path = self.select_image_file()
        self.initialize_image(image_file_path)

    # 이미지 파일 선택
    def select_image_file(self) -> str:
        root = tk.Tk()
        root.withdraw()
        image_file_path = filedialog.askopenfilename(
            initialdir=os.path.join(os.getcwd(), "images"),
            title="Select a image",
            filetypes=[("Image Files", "*.png;*.jpg;*.jpeg")],
        )
        root.destroy()

        if not image_file_path:
            raise ValueError("No image file selected.")

        return image_file_path

    # 이미지 초기 설정
    def initialize_image(self, image_file_path: str):
        self.image_list.clear()
        self.image_index = 0

        original_image = cv.imread(image_file_path)

        self.image_list.append(original_image)
        self.image_list.append(
            CartoonRenderer.get_cartoon_rendered_image_1(original_image)
        )
        self.image_list.append(
            CartoonRenderer.get_cartoon_rendered_image_2(original_image)
        )

    # 프로그램 실행
    def run(self):
        self.display_image_and_handle_key()

    # 이미지 출력 및 키 입력 대기
    def display_image_and_handle_key(self):
        cv.imshow(self.WINDOW_TITLE, self.image_list[self.image_index])
        self.handle_key_input(cv.waitKey(0))

    # 키 입력 이벤트 관리
    def handle_key_input(self, keycode: int):
        # 새로운 이미지 파일 선택
        if keycode == KEYCODE_DICT["enter"]:
            print("Select New Image File")
            image_file_path = self.select_image_file()
            self.initialize_image(image_file_path)
            self.display_image_and_handle_key()
        # 필터 전환
        elif keycode == KEYCODE_DICT["space"]:
            self.image_index += 1
            self.image_index %= len(self.image_list)
            print(f"Switch Filter: version {self.image_index}")
            self.display_image_and_handle_key()
        # 프로그램 종료
        elif keycode == KEYCODE_DICT["esc"]:
            print("Exit Program")
            cv.destroyAllWindows()

    # 카툰 렌더링 버전 1
    @staticmethod
    def get_cartoon_rendered_image_1(image) -> np.ndarray:
        # 1) Bilateral filter로 영역 내부를 부드럽게 하되 색 경계는 보존
        smoothed = cv.bilateralFilter(image, d=9, sigmaColor=80, sigmaSpace=80)

        # 2) 포스터라이즈로 색면 단순화
        levels = 6
        step = 256 // levels
        posterized = (smoothed.astype(np.int16) // step) * step + step // 2
        posterized = np.clip(posterized, 0, 255).astype(np.uint8)

        # 3) Laplacian 기반 경계 강화: 밝기 증가는 막고 경계는 조금 더 두껍게
        gray = cv.cvtColor(posterized, cv.COLOR_BGR2GRAY)
        lap = cv.Laplacian(gray, cv.CV_32F, ksize=3)
        edge_strength = cv.convertScaleAbs(np.abs(lap))
        edge_strength = cv.GaussianBlur(edge_strength, (5, 5), 0)

        edge_alpha = (edge_strength.astype(np.float32) / 255.0) * 0.5
        edge_alpha_3 = cv.cvtColor(edge_alpha, cv.COLOR_GRAY2BGR)

        result = posterized.astype(np.float32) * (1.0 - edge_alpha_3)
        return np.clip(result, 0, 255).astype(np.uint8)

    # 카툰 렌더링 버전 2
    @staticmethod
    def get_cartoon_rendered_image_2(image) -> np.ndarray:
        # 1) Gaussian smoothing으로 노이즈를 줄이고 색면화를 준비
        smoothed = cv.GaussianBlur(image, (9, 9), 0)

        # 2) K-means로 색상 수를 줄여 만화식 색면 단순화
        h, w = smoothed.shape[:2]
        pixels = smoothed.reshape((-1, 3)).astype(np.float32)
        k = 5
        criteria = (cv.TERM_CRITERIA_EPS + cv.TERM_CRITERIA_MAX_ITER, 25, 1.0)
        _, labels, centers = cv.kmeans(
            pixels,
            k,
            None,
            criteria,
            5,
            cv.KMEANS_PP_CENTERS,
        )
        centers = np.uint8(centers)
        quantized = centers[labels.flatten()].reshape((h, w, 3))

        # 3) Scharr gradient로 경계 추출 (허용된 edge detector 사용)
        gray = cv.cvtColor(smoothed, cv.COLOR_BGR2GRAY)
        grad_x = cv.Scharr(gray, cv.CV_32F, 1, 0)
        grad_y = cv.Scharr(gray, cv.CV_32F, 0, 1)
        magnitude = cv.magnitude(grad_x, grad_y)
        magnitude = cv.convertScaleAbs(magnitude)

        # Otsu threshold로 이미지별로 경계 강도를 자동 조절
        _, edges = cv.threshold(magnitude, 0, 255, cv.THRESH_BINARY + cv.THRESH_OTSU)

        # 미세한 끊김을 줄이고 경계를 약간만 또렷하게
        edges = cv.morphologyEx(
            edges,
            cv.MORPH_OPEN,
            np.ones((3, 3), dtype=np.uint8),
            iterations=1,
        )
        edges = cv.dilate(edges, np.ones((1, 1), dtype=np.uint8), iterations=1)

        # 4) 색면 위에 검은 경계를 합성
        edges_inv = cv.bitwise_not(edges)
        edges_inv_bgr = cv.cvtColor(edges_inv, cv.COLOR_GRAY2BGR)
        return cv.bitwise_and(quantized, edges_inv_bgr)
