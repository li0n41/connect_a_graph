#!/usr/bin/python
# -*- coding: utf-8
# Copyright 2018, github/li0n41, All rights reserved.
#
# Usages:
# 1) Puzzle generation
# $ ./connect_a_graph.py <height> <width> <num_cells>
# 2) Puzzle solution
# $ ./connect_a_graph.py <height> <width> <comma_separate_list_of_positions_of_removed_cells> <starting_position>
#   positions are in the format of "<row_num>:<col_num>". Both numbers start from 1.

import itertools
import math
import sys
import time

class Direction(object):
	UP = 0
	DOWN = 1
	LEFT = 2
	RIGHT = 3

class Chars(object):
	START = {Direction.UP: '╨',
			 Direction.DOWN: '╥',
			 Direction.LEFT: '╡',
			 Direction.RIGHT: '╞'}
	END = {Direction.UP: '╥',
		   Direction.DOWN: '╨',
		   Direction.LEFT: '╞',
		   Direction.RIGHT: '╡'}
	PATH = {(Direction.UP, Direction.UP): '║',
			(Direction.DOWN, Direction.DOWN): '║',
			(Direction.LEFT, Direction.LEFT): '═',
			(Direction.RIGHT, Direction.RIGHT): '═',
			(Direction.UP, Direction.LEFT): '╗',
			(Direction.RIGHT, Direction.DOWN): '╗',
			(Direction.DOWN, Direction.RIGHT): '╚',
			(Direction.LEFT, Direction.UP): '╚',
			(Direction.LEFT, Direction.DOWN): '╔',
			(Direction.UP, Direction.RIGHT): '╔',
			(Direction.RIGHT, Direction.UP): '╝',
			(Direction.DOWN, Direction.LEFT): '╝'}
	BACKGROUND = '*'
	BOARD = {0: ' ', 1: '█'}

# Data model
# We use a number to store states of the board.
# For an M x N board, we need M*N many bits, one bit for each cell.
# - Mark each row from 0 to M - 1, and each column from 0 to N - 1.
# - Each cell can be represented by a coordinate (i, j), where i is the cell's
#   row number, and j is column number. Then the (i * M + j)-th bit represents
#   the state of (i, j), i.e. 1 means set, 0 means unset. So a number with M*N
#   bits can represent the entire board.
# The limitation is basically how many bits can a Python integer has.
# Per https://docs.python.org/3.1/whatsnew/3.0.html#integers, there's no limit
# on integer in Python 3. Still worth verifying if underlying addresses for
# storing integer is unlimited (as long as the system can allocate).

class Masks(object):
	"""Masks to extract bits of each row and column.
	
	Attributes:
		rows: A list of masks. i-th mask extracts bits of i-th row.
		cols: A list of masks. i-th mask extracts bits of i-th column.
	"""
	def __init__(self, height, width):
		self.rows = []
		one_row = 0
		for _ in range(width):
			one_row <<= 1
			one_row |= 1
		for _ in range(height):
			self.rows.append(one_row)
			one_row <<= width

		self.cols = []
		one_col = 0
		for _ in range(height):
			one_col <<= width
			one_col |= 1
		for _ in range(width):
			self.cols.append(one_col)
			one_col <<= 1


class Helper(object):
	def __init__(self, height, width):
		self.height = height
		self.width = width
		self.masks = Masks(height, width)
	
	def EncodePosition(self, row, col):
		"""Use a single number to represent a location in board.
		
		Basically set i-th cell's corresponding bit to 1, and other bits to 0.
		"""
		return 1 << (self.width * row + col)

	def DecodePosition(self, position):
		"""Reverse of EncodePosition(). Assume the given position is valid."""
		shift = position.bit_length() - 1
		row = shift / self.width
		col = shift % self.width
		return row, col

	def PrintBoard(self, board, position):
		"""'board' indicates which cells are set. 'position' is starting cell."""
		mask = 1
		rows = []
		for _ in range(self.height):
			row = ''
			for _ in range(self.width):
				cell_str = Chars.BOARD[1 if board & mask > 0 else 0]
				if position & mask > 0:
					cell_str = Chars.BACKGROUND
				row += cell_str
				mask <<= 1
			rows.append(row)
		print('\n'.join(rows))

	def Move(self, board, position, direction):
		"""Returns new position after moving along the given direction by 1 cell
		from given starting position. Returns None if there's no available cell
		to move.
		"""
		new_position = self.GetPositionAfterMove(position, direction)
		if new_position is None:
			# Out of bound.
			return None
		if new_position & board == 0:
			# Cell is not available to visit (either not set in the initial
			# puzzle or has been visited.
			return None
		return new_position

	def GetPositionAfterMove(self, position, direction):
		offset = position.bit_length() - 1
		if direction == Direction.UP:
			return position >> self.width if offset >= self.width else None
		elif direction == Direction.DOWN:
			return (position << self.width
					if offset < (self.width * (self.height - 1))
					else None)
		elif direction == Direction.LEFT:
			return position >> 1 if offset % self.width > 0 else None
		return position << 1 if offset % self.width < (self.width - 1) else None
		assert False
		return None

	def IsBoardPossible(self, board):
		if board == 0:
			# Empty board.
			return False
		# Number of odd cells and even cells should not differ more than 1.
		# Here, odd bits means that the sum of coordinate of the cell is an odd
		# number. Similar for even bits. e.g. (0, 1) is an odd cell, (0, 0) is
		# an even cell. This is because when moving horizontally / vertically by
		# 1 cell, we either move from an odd cell to an even cell, or from an
		# even cell to an odd cell.
		num_cells = [0, 0]
		visited = []
		for row in range(self.height):
			for col in range(self.width):
				position = self.EncodePosition(row, col)
				if board & position > 0:
					num_cells[(row + col) % 2] += 1
					if not visited:
						# Find the first visited cell. Used for checking
						# connection later.
						visited.append(position)
		if abs(num_cells[0] - num_cells[1]) > 1:
			return False
		# Traverse cells to see if all cells are connected.
		# It's basically a BFS from the first visited cell found above.
		# Record all cells visited. If it's the same as board, it means the
		# board is connected. Otherwise the board is not connected, i.e. there's
		# aways a cell that cannot be reached regardless where to start.
		visited_bits = 0
		def visit(position, direction):
			new_position = self.Move(board, position, direction)
			if (new_position and (visited_bits & new_position == 0)):
				visited.append(new_position)
		while visited:
			position = visited.pop(0)
			visited_bits |= position
			visit(position, Direction.UP)
			visit(position, Direction.DOWN)
			visit(position, Direction.LEFT)
			visit(position, Direction.RIGHT)
		return board == visited_bits

	def Size(self, board):
		"""Calculate how many cells are still set in board."""
		mask = 1
		size = 0
		for _ in range(board.bit_length()):
			if board & mask > 0:
				size += 1
			mask <<= 1
		return size

	def _Solve(self, board, position, path):
		# Not a valid position.
		if position is None:
			return False
		# Current position doesn't have a cell available, i.e. not set.
		if board & position == 0:
			return False
		if not self.IsBoardPossible(board):
			return False
		path.append(position)
		# Recurrsion stop condition: One cell left.
		if self.Size(board) == 1:
			return True
		# Unset current cell's bit, meaning we've visited it.
		board &= ~position
		# Try visiting 4 directions to see if there's a solution for the sub-problem.
		if (self._Solve(board, self.Move(board, position, Direction.UP), path) or
			self._Solve(board, self.Move(board, position, Direction.DOWN), path) or
			self._Solve(board, self.Move(board, position, Direction.LEFT), path) or
			self._Solve(board, self.Move(board, position, Direction.RIGHT), path)):
			return True
		path.pop()
		return False

	def Solve(self, board, position):
		path = []
		self._Solve(board, position, path)
		return path

	def RenderPath(self, path):
		if len(path) == 0:
			print('No solution')
			return
		def DirectionFromTo(node1, node2):
			diff1 = node1 // node2
			diff2 = node2 // node1
			if diff1 == 0 and diff2 == 2:
				return Direction.RIGHT
			if diff1 == 0 and diff2 == 2 ** self.width:
				return Direction.DOWN
			if diff2 == 0 and diff1 == 2:
				return Direction.LEFT
			if diff2 == 0 and diff1 == 2 ** self.width:
				return Direction.UP
			assert False
			return None
		board = []
		for _ in range(self.height):
			board.append([Chars.BACKGROUND] * self.width)
		assert len(path) > 1
		for i in range(len(path)):
			row, col = self.DecodePosition(path[i])
			if i == 0:
				board[row][col] = Chars.START[DirectionFromTo(path[i], path[i+1])]
			elif i == len(path) - 1:
				board[row][col] = Chars.END[DirectionFromTo(path[i-1], path[i])]
			else:
				board[row][col] = Chars.PATH[(DirectionFromTo(path[i-1], path[i]),
					                          DirectionFromTo(path[i], path[i+1]))]
		print('\n'.join([''.join(row) for row in board]))

	def ParsePosition(self, position_str):
		"""Position format "<row>:<col>". ""Here, row and col numbers start from 1."""
		tokens = position_str.split(':')
		assert len(tokens) == 2
		row = int(tokens[0]) - 1
		col = int(tokens[1]) - 1
		return self.EncodePosition(row, col)

	def ParseBoard(self, board_str):
		board = int('1' * (self.width * self.height), 2)
		position_strs = board_str.split(',')
		for position_str in position_strs:
			board &= ~(self.ParsePosition(position_str))
		return board

	def FindAllPuzzles(self, num):
		"""Find all possible boards with num cells."""
		itr = 0
		found = 0
		all_cells = self.width * self.height
		# Combination_{all_cells}^{num} many possible boards.
		all_num = (math.factorial(all_cells) / math.factorial(all_cells - num) /
				   math.factorial(num))
		start_time = time.time()
		for board in self.GetAllPossibleBoards(num):
			# Skip duplicate boards that have been solved.
			# Skip impossible boards.
			if (not self.DeduplicateBoard(board) == board or
			    not self.IsBoardPossible(board)):
				# Skipping 'num' many possible puzzles (one board with 'num'
				# many possible starting position).
				itr += num
				continue
			# Iterate through all possible starting position.
			for row in range(self.height):
				for col in range(self.width):
					start_position = self.EncodePosition(row, col)
					if board & start_position == 0:
						continue
					itr += 1
					path = self.Solve(board, start_position)
					self.PrintBoard(board, start_position)
					print '(%d, %d)' % (row + 1, col + 1)
					if path:
						self.RenderPath(path)
						found += 1
					else:
						print 'No result. Pass.'
					now = time.time()
					print 'Iterated %d, found %d, all %d' % (itr, found, all_num * num)
					print 'Time passed: %d seconds; ETA: %d hours' % (
							now - start_time,
							(now - start_time) / itr * all_num * num // 3600)

	def DeduplicateBoard(self, board):
		"""Find the encoding of the unique board.
		
		Some board may have exactly the same shape as another, but just has
		some horizontal / vertical shift. Here we move all boards towards left
		and up to eliminate empty columns and rows, and use the encoding of this
		"top-left-aligned" board as key to represent a unique shape.

		For example, 2x2 board:
		10     00     01     00
		00     10     00     01
		Are considered boards with the shape.
		- If moving the 1st board down by 1 cell, it's the 2nd board. 
		- If moving the 1st board rigth by 1 cell, it's the 3rd board. 
		- If moving the 1st board down and right by 1 cell, it's the 4th board. 
		So we use the encoding of the 1st board as key for all 4 boards, because
		they share the same solution.
		"""
		if board == 0:
			return board
		first_non_empty_row = 0
		for row_mask in self.masks.rows:
			if row_mask & board > 0:
				break
			first_non_empty_row += 1
		first_non_empty_col = 0
		for col_mask in self.masks.cols:
			if col_mask & board > 0:
				break
			first_non_empty_col += 1
		return board >> (first_non_empty_row * self.width + first_non_empty_col)

	def GetAllPossibleBoards(self, num):
		"""Get all possible boards with num many cells."""
		for positions in itertools.combinations(
				list(range(self.width * self.height)), num):
			board = 0
			for pos in positions:
				board |= (1 << pos)
			yield board


def main():
	height = int(sys.argv[1])
	width = int(sys.argv[2])
	helper = Helper(height, width)

	if len(sys.argv) == 4:
		num = int(sys.argv[3])
		helper.FindAllPuzzles(num)
	elif len(sys.argv) == 5:
		board = helper.ParseBoard(sys.argv[3])
		position = helper.ParsePosition(sys.argv[4])
		helper.PrintBoard(board, position)
		print
		path = helper.Solve(board, position)
		helper.RenderPath(path)

if __name__ == "__main__":
	main()
