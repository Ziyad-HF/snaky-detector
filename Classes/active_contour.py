import cv2
import numpy as np


# Run edge detection on image
def get_img_edges(img):
    return cv2.Canny(img, 30, 150)


# Normalize array to values from 0-1
def norm_0_1(arr):
    maximum = np.amax(arr)

    if maximum == 0:
        return arr

    return arr / np.amax(arr)


def add_border(arr):
    return np.pad(arr, pad_width=2, mode='constant', constant_values=255)


class ContourPoint:
    def __init__(self, row, col):
        self.row = row
        self.col = col
        self.chain_code = []

        # Must combine energies so that:
        # 	contour grows/shrinks
        # 	contour points remain equidistant
        # 	contour points prioritize lines

        # Total Energies
        self.energies = np.empty((7, 7), dtype=float)

    # Calculates energies to move points away from each other
    # 	Moves to point which is furthest from all contour points
    def calc_energy_distance(self, contour_r, contour_c, shrink=False):
        r = self.row
        c = self.col

        energy_distance = np.zeros((7, 7), dtype=float)

        for i in range(-3, 4):
            for j in range(-3, 4):
                # (x2 - x1)^2 + (y2 - y1)^2
                energy_distance[i + 3, j + 3] = np.sum(np.square((r + i) - contour_r) + np.square((c + j) - contour_c))

        if shrink:
            self.energies = np.dstack((self.energies, norm_0_1(energy_distance)))
        else:
            self.energies = np.dstack((self.energies, 1.0 - norm_0_1(energy_distance)))

    # Attempts to move points to center of neighbors
    def calc_energy_deviation(self, prior_point, next_point):
        r = self.row
        c = self.col

        energy_deviation = np.zeros((7, 7), dtype=float)

        for i in range(-3, 4):
            for j in range(-3, 4):
                d2n = np.square(r + i - next_point.row) + np.square(c + j - next_point.col)
                d2p = np.square(r + i - prior_point.row) + np.square(c + j - prior_point.col)

                energy_deviation[i + 3, j + 3] = np.power(np.absolute(d2n - d2p), 2)

        self.energies = np.dstack((self.energies, norm_0_1(energy_deviation)), )

    # Pulls contour to higher values on grayscale image
    def calc_energy_gradient(self, img, to_low=False):
        r = self.row
        c = self.col

        energy_gradient = np.zeros((7, 7), dtype=float)

        for i in range(-3, 4):
            for j in range(-3, 4):
                new_r = r + i
                new_c = c + j

                if new_r >= img.shape[0]:
                    new_r = img.shape[0] - 1

                if new_c >= img.shape[1]:
                    new_c = img.shape[1] - 1
                print("Indices:", new_r, new_c, "image shape:", img.shape)
                energy_gradient[i + 3, j + 3] = np.square(img[new_r, new_c])

        if to_low:
            self.energies = np.dstack((self.energies, norm_0_1(energy_gradient)))
        else:
            self.energies = np.dstack((self.energies, 1.0 - norm_0_1(energy_gradient)))

    # add all energies in contour
    def add_energies(self):
        self.energies = np.sum(self.energies, axis=2)

    def adjust_point(self):
        minimum_energy = np.argmin(self.energies)

        # 0,0 : 0,1 : 0,2 : 0,3 : 0,4 : 0,5 : 0,6
        # 1,0 : 1,1 : 1,2 : 1,3 : 1,4 : 1,5 : 1,6
        # 2,0 : 2,1 : 2,2 : 2,3 : 2,4 : 2,5 : 2,6
        # 3,0 : 3,1 : 3,2 : 3,3 : 3,4 : 3,5 : 3,6
        # 4,0 : 4,1 : 4,2 : 4,3 : 4,4 : 4,5 : 4,6
        # 5,0 : 5,1 : 5,2 : 5,3 : 5,4 : 5,5 : 5,6
        # 6,0 : 6,1 : 6,2 : 6,3 : 6,4 : 6,5 : 6,6

        # Add row adjustment, is shift from center, 3,3 on 7x7 kernel
        self.row += minimum_energy // 7 - 3
        # Add column adjustment, same deal as row adjust
        self.col += minimum_energy % 7 - 3

    def calculate_chain_code(self, next_point):
        # Calculate direction from current point to the next point
        dx = next_point.col - self.col
        dy = next_point.row - self.row

        # Determine the chain code based on the direction
        if dx == 1 and dy == 0:
            code = 0
        elif dx == 1 and dy == 1:
            code = 1
        elif dx == 0 and dy == 1:
            code = 2
        elif dx == -1 and dy == 1:
            code = 3
        elif dx == -1 and dy == 0:
            code = 4
        elif dx == -1 and dy == -1:
            code = 5
        elif dx == 0 and dy == -1:
            code = 6
        elif dx == 1 and dy == -1:
            code = 7
        else:
            code = -1  # Invalid code

        # Store the chain code in the chain_code attribute
        self.chain_code.append(code)

    # Draws a single point in the contour
    def draw_point(self, img, val=255, w1=15, w2=4):
        '''Draws a cross on image at point in image'''
        img[self.row - w1 // 2:self.row + w1 // 2 + 1, self.col - w2 // 2:self.col + w2 // 2 + 1] = val
        img[self.row - w2 // 2:self.row + w2 // 2 + 1, self.col - w1 // 2:self.col + w1 // 2 + 1] = val


class Contour:
    def __init__(self, contour=None):
        self.contour = []
        self.contour_r = []
        self.contour_c = []
        self.average_distance = 0.0

        if np.all(contour != None):
            for point in contour:
                self.contour_r.append(point[0])
                self.contour_c.append(point[1])
                self.contour.append(ContourPoint(point[0], point[1]))

            self.contour_r = np.array(self.contour_r)
            self.contour_c = np.array(self.contour_c)
            self.contour = np.array(self.contour)

            tmp_r = np.roll(np.copy(self.contour_r), 1)
            tmp_c = np.roll(np.copy(self.contour_c), 1)

            self.average_distance = np.average(
                np.sqrt(np.power(self.contour_r - tmp_r, 2) + np.power(self.contour_c - tmp_c, 2)))

    def draw_contour(self, img, val=0, w1=15, w2=2):
        '''Draws each point in contour and line between them'''
        for i in range(len(self.contour)):
            self.contour[i].draw_point(img)

            cv2.line(
                img,
                (self.contour_c[i], self.contour_r[i]),
                (self.contour_c[(i + 1) % len(self.contour_c)], self.contour_r[(i + 1) % len(self.contour_r)]),
                val, 1)

    def calc_energies(self, img):
        for i, point in enumerate(self.contour):
            next_point = self.contour[(i + 1) % len(self.contour)]

            if i == 0:
                prior_point = self.contour[-1]
            else:
                prior_point = self.contour[i - 1]

            point.energies = np.zeros((7, 7))

            point.calc_energy_distance(self.contour_r, self.contour_c)
            point.calc_energy_deviation(prior_point, next_point)
            point.calc_energy_gradient(img)

            point.add_energies()

    def update_points(self):
        self.contour_r = []
        self.contour_c = []

        for i, point in enumerate(self.contour):
            point.adjust_point()

            self.contour_r.append(point.row)
            self.contour_c.append(point.col)

            # Calculate chain code for the current point
            next_point = self.contour[(i + 1) % len(self.contour)]
            point.calculate_chain_code(next_point)

        self.contour_r = np.array(self.contour_r)
        self.contour_c = np.array(self.contour_c)
        self.contour = np.array(self.contour)

        tmp_r = np.roll(np.copy(self.contour_r), 1)
        tmp_c = np.roll(np.copy(self.contour_c), 1)

        self.average_distance = np.average(
            np.sqrt(np.power(self.contour_r - tmp_r, 2) + np.power(self.contour_c - tmp_c, 2)))

    # def update_points(self):
    #     self.contour_r = []
    #     self.contour_c = []
    #
    #     for point in self.contour:
    #         point.adjust_point()
    #
    #         self.contour_r.append(point.row)
    #         self.contour_c.append(point.col)
    #
    #     self.contour_r = np.array(self.contour_r)
    #     self.contour_c = np.array(self.contour_c)
    #     self.contour = np.array(self.contour)
    #
    #     tmp_r = np.roll(np.copy(self.contour_r), 1)
    #     tmp_c = np.roll(np.copy(self.contour_c), 1)
    #
    #     self.average_distance = np.average(
    #         np.sqrt(np.power(self.contour_r - tmp_r, 2) + np.power(self.contour_c - tmp_c, 2)))

    def insert_points(self):
        tmp_contour = []

        for i, point in enumerate(self.contour):
            next_row = (point.row + (self.contour[(i + 1) % len(self.contour)].row)) // 2
            next_col = (point.col + (self.contour[(i + 1) % len(self.contour)].col)) // 2

            tmp_contour.append(point)
            tmp_contour.append(ContourPoint(next_row, next_col))

        self.contour = tmp_contour
        self.contour_r = []
        self.contour_c = []

        for point in self.contour:
            self.contour_r.append(point.row)
            self.contour_c.append(point.col)

        self.contour_r = np.array(self.contour_r)
        self.contour_c = np.array(self.contour_c)
        self.contour = np.array(self.contour)

        tmp_r = np.roll(np.copy(self.contour_r), 1)
        tmp_c = np.roll(np.copy(self.contour_c), 1)

        self.average_distance = np.average(
            np.sqrt(np.power(self.contour_r - tmp_r, 2) + np.power(self.contour_c - tmp_c, 2)))
