# 附录 B：论文演示用途 Python 代码
# 两门编程语言逻辑一致，全部手动实现，可以复现结果的代码

import string
import random
import hashlib
import sys
from typing import List, Dict, Any

ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
ALPHABET_SIZE = len(ALPHABET)

def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode('utf-8')).hexdigest()

def generate_seed(key: str) -> int:
    # For reproducibility: interpret key as hex and mod 2**32
    return int(sha256_hex(key), 16) % (2 ** 32)

class MT19937:
    # Python implementation of MT19937
    N = 624
    M = 397
    A = 0x9908B0DF
    UPPER_MASK = 0x80000000
    LOWER_MASK = 0x7FFFFFFF

    def __init__(self, seed: int):
        self.mt = [0] * self.N
        self.index = self.N
        self.mt[0] = seed & 0xFFFFFFFF
        for i in range(1, self.N):
            prev = self.mt[i - 1]
            self.mt[i] = (1812433253 * (prev ^ (prev >> 30)) + i) & 0xFFFFFFFF

    def _twist(self):
        for i in range(self.N):
            x = (self.mt[i] & self.UPPER_MASK) + (self.mt[(i + 1) % self.N] & self.LOWER_MASK)
            xA = x >> 1
            if x & 1:
                xA ^= self.A
            self.mt[i] = self.mt[(i + self.M) % self.N] ^ xA
        self.index = 0

    def extract(self) -> int:
        if self.index >= self.N:
            self._twist()
        y = self.mt[self.index]
        y ^= (y >> 11)
        y ^= (y << 7) & 0x9D2C5680
        y ^= (y << 15) & 0xEFC60000
        y ^= (y >> 18)
        self.index += 1
        return y & 0xFFFFFFFF

    def rand_int(self, lo: int, hi: int) -> int:
        if hi < lo:
            lo, hi = hi, lo
        return lo + (self.extract() % (hi - lo + 1))

    def shuffle(self, vec: List[Any]) -> None:
        for i in range(len(vec) - 1, 0, -1):
            j = self.rand_int(0, i)
            vec[i], vec[j] = vec[j], vec[i]

    def sample(self, vec: List[Any], k: int) -> List[Any]:
        tmp = vec[:]
        self.shuffle(tmp)
        return tmp[:min(k, len(tmp))]


class Rotor:
    def __init__(self, mapping: List[str], rotor_type: str):
        self.mapping = mapping
        self.rotor_type = rotor_type
        # build inverse mapping
        self.inverse = {self.mapping[i]: ALPHABET[i] for i in range(ALPHABET_SIZE)}
        self.position = 0

    def map_forward(self, c: str) -> str:
        idx = ALPHABET.index(c)
        mapped = self.mapping[(idx + self.position) % ALPHABET_SIZE]
        out_idx = (ALPHABET.index(mapped) - self.position) % ALPHABET_SIZE
        return ALPHABET[out_idx]

    def map_backward(self, c: str) -> str:
        idx = ALPHABET.index(c)
        # apply inverse at rotated position
        inv_input = ALPHABET[(idx + self.position) % ALPHABET_SIZE]
        mapped = self.inverse[inv_input]
        out_idx = (ALPHABET.index(mapped) - self.position) % ALPHABET_SIZE
        return ALPHABET[out_idx]

    def __str__(self) -> str:
        pos_char = ALPHABET[self.position]
        return f"{self.rotor_type} Rotor (pos={pos_char})"


class EnhancedEnigma:
    def __init__(self, key: str):
        self.key = key
        self.seed = generate_seed(key)
        self.rng = MT19937(self.seed)

        # 4 rotors: derangement, partial(10), derangement, partial(7)
        self.rotors: List[Rotor] = [
            self._create_rotor(derange=True),
            self._create_rotor(derange=False, fixed_pts=10),
            self._create_rotor(derange=True),
            self._create_rotor(derange=False, fixed_pts=7)
        ]

        # reflector with 6 fixed loops
        self.reflector = self._create_reflector(loops=6)

        # initial positions from SHA-256 digest
        self.positions = self._derive_positions(self.key, count=4)
        self._reset_positions()

    def _create_rotor(self, derange: bool, fixed_pts: int = 0) -> Rotor:
        if derange:
            perm = self._generate_derangement()
            return Rotor(perm, "Derangement")
        else:
            perm = self._generate_partial_derangement(fixed_pts)
            return Rotor(perm, f"Partial Derangement(fixed={fixed_pts})")

    def _generate_derangement(self) -> List[str]:
        while True:
            perm = list(ALPHABET)
            self.rng.shuffle(perm)
            if all(perm[i] != ALPHABET[i] for i in range(ALPHABET_SIZE)):
                return perm

    def _generate_partial_derangement(self, fixed_points: int) -> List[str]:
        # 限制 fixed_points 在合理区间
        fixed_points = max(1, min(fixed_points, 26-2))
        
        # 1. 随机选定 k 个固定点位置
        fixed_positions = set(self.rng.sample(list(range(26)), fixed_points))
        
        # 2. 准备结果列表
        perm = [None] * 26
        
        # 3. 对固定点位置，直接赋值
        for i in fixed_positions:
            perm[i] = ALPHABET[i]
        
        # 4. 处理剩下的位置：做一个无固定点排列
        other_positions = [i for i in range(26) if i not in fixed_positions]
        other_chars     = [ALPHABET[i] for i in other_positions]
        
        # 随机生成一个完全无固定点排列
        while True:
            self.rng.shuffle(other_chars)
            # 检查是否有固定点
            if all(other_chars[j] != ALPHABET[other_positions[j]]
                   for j in range(len(other_positions))):
                break
        
        # 5. 填回结果
        for idx, pos in enumerate(other_positions):
            perm[pos] = other_chars[idx]
        
        return perm

    def _create_reflector(self, loops: int) -> List[str]:
        idx = list(range(ALPHABET_SIZE))
        self.rng.shuffle(idx)
        loopset = set(idx[:loops])
        mapping = [None] * ALPHABET_SIZE
        free = idx[loops:]
        # pair up
        while len(free) > 1:
            i = free.pop()
            j = free.pop()
            mapping[i] = ALPHABET[j]
            mapping[j] = ALPHABET[i]
        # fixed loops
        for i in loopset:
            mapping[i] = ALPHABET[i]
        return mapping  # list of 26 chars

    def _derive_positions(self, key: str, count: int) -> List[int]:
        h = sha256_hex(key)
        pos = []
        for i in range(count):
            byte = h[2*i:2*i+2]
            pos.append(int(byte, 16) % ALPHABET_SIZE)
        return pos

    def _reset_positions(self):
        for i, r in enumerate(self.rotors):
            r.position = self.positions[i]

    def _rotate_rotors(self):
        # like odometer
        for i in range(len(self.rotors)):
            r = self.rotors[i]
            r.position = (r.position + 1) % ALPHABET_SIZE
            if r.position != 0:
                break

    def _process(self, text: str, use_plugboard: bool = False,
                 plugboard: Dict[str, str] = None) -> str:
        out = []
        for c in text:
            if c not in ALPHABET:
                out.append(c)
                continue
            # plugboard in
            if use_plugboard:
                c = plugboard.get(c, c)
            self._rotate_rotors()
            # forward through rotors
            for r in self.rotors:
                c = r.map_forward(c)
            # reflector
            c = self.reflector[ALPHABET.index(c)]
            # back through rotors
            for r in reversed(self.rotors):
                c = r.map_backward(c)
            # plugboard out
            if use_plugboard:
                c = plugboard.get(c, c)
            out.append(c)
        return "".join(out)

    def encrypt(self, plaintext: str) -> str:
        return self._process(plaintext)

    def decrypt(self, ciphertext: str) -> str:
        self._reset_positions()
        return self._process(ciphertext)

    def __str__(self) -> str:
        s = [f"Enhanced Enigma (Key={self.key})"]
        for i, r in enumerate(self.rotors, 1):
            s.append(f" Rotor {i}: {r}")
        s.append(" Reflector: " + "".join(self.reflector))
        return "\n".join(s)


class EnhancedEnigmaWithPlugboard(EnhancedEnigma):
    def __init__(self, key: str, plug_pairs: int = 0):
        super().__init__(key)
        # create plugboard mapping
        self.plugboard: Dict[str, str] = {c: c for c in ALPHABET}
        letters = list(ALPHABET)
        self.rng.shuffle(letters)
        cnt = max(0, min(13, plug_pairs))
        for i in range(cnt):
            a, b = letters[2*i], letters[2*i+1]
            self.plugboard[a] = b
            self.plugboard[b] = a

    def encrypt(self, plaintext: str) -> str:
        return self._process(plaintext, use_plugboard=True, plugboard=self.plugboard)

    def decrypt(self, ciphertext: str) -> str:
        self._reset_positions()
        return self._process(ciphertext, use_plugboard=True, plugboard=self.plugboard)


if __name__ == "__main__":
    key1 = "MySecretKey123!"
    enigma = EnhancedEnigma(key1)
    print(enigma)
    pt = "ENHANCED ENIGMA MACHINE SECURITY"
    ct = enigma.encrypt(pt)
    print("Ciphertext:", ct)
    print("Decrypted:", enigma.decrypt(ct))
    print("Match:", pt == enigma.decrypt(ct))

    key2 = "MathCodePlugbard2025"
    plug_enigma = EnhancedEnigmaWithPlugboard(key2, plug_pairs=6)
    sample = "THE QUICK BROWN FOX JUMPS OVER THE LAZY DOG"
    enc2 = plug_enigma.encrypt(sample)
    dec2 = plug_enigma.decrypt(enc2)
    print("\nWith Plugboard:")
    print("Ciphertext:", enc2)
    print("Decrypted:", dec2)
    print("Match:", sample == dec2)
