# 附录 A：论文演示用途 Python 代码

import string
import random
import hashlib
from typing import Callable, Dict, List, Tuple

# Define the alphabet
alphabet = string.ascii_uppercase

class EnhancedEnigma:
    def __init__(self, key):
        """
        Enhanced Enigma Machine
        :param key: Encryption key used to generate all components
        """
        self.key = key
        self.seed = self._generate_seed(key)
        random.seed(self.seed)
        
        # Create four rotors: derangement -> partial derangement -> derangement -> partial derangement
        self.rotor1 = self._create_rotor(derangement=True)
        self.rotor2 = self._create_rotor(derangement=False, fixed_points=10)
        self.rotor3 = self._create_rotor(derangement=True)
        self.rotor4 = self._create_rotor(derangement=False, fixed_points=7)
        
        # Create the reflector
        self.reflector = self._create_reflector(self_loops=6)
        
        # Set initial rotor positions
        self.positions = self._derive_positions(key, 4)
        self.reset_positions()
    
    def _generate_subkey(self, key):
        """Generate a subkey (SHA-256 digest) from the key"""
        return hashlib.sha256(key.encode()).hexdigest()
    
    def _generate_seed(self, key):
        """Generate a random seed from the key"""
        return int(self._generate_subkey(key), 16) % (2**32)
    
    def _derive_positions(self, key, count):
        """Derive initial rotor positions from the key"""
        positions = []
        hash_val = self._generate_subkey(key)
        
        # Each 2 hex digits correspond to one position
        for i in range(0, min(count * 2, len(hash_val)), 2):
            hex_pair = hash_val[i:i+2]
            positions.append(int(hex_pair, 16) % len(alphabet))
        
        # If not enough positions, pad with zeros
        while len(positions) < count:
            positions.append(0)
        
        return positions[:count]
    
    def reset_positions(self):
        """Reset rotors to initial positions"""
        self.rotor1.position = self.positions[0]
        self.rotor2.position = self.positions[1]
        self.rotor3.position = self.positions[2]
        self.rotor4.position = self.positions[3]
    
    def _create_rotor(self, derangement=True, fixed_points=10):
        """
        Create a rotor
        :param derangement: True for derangement rotor, False for partial derangement rotor
        :param fixed_points: Number of fixed points for partial derangement rotor
        """
        if derangement:
            mapping = self._generate_derangement()
            rotor_type = "Derangement"
        else:
            mapping = self._generate_partial_derangement(fixed_points)
            rotor_type = f"Partial Derangement (fixed={fixed_points})"
        
        return self.Rotor(mapping, rotor_type)
    
    def _generate_derangement(self):
        """Generate a derangement (permutation with no fixed points)"""
        while True:
            perm = list(alphabet)
            random.shuffle(perm)
            if all(perm[i] != alphabet[i] for i in range(len(alphabet))):
                return perm
    
    def _generate_partial_derangement(self, fixed_points):
        """Generate a partial derangement permutation"""
        if fixed_points < 1 or fixed_points > 24:
            fixed_points = 13
        
        # Randomly select positions for fixed points
        fixed_positions = random.sample(range(len(alphabet)), fixed_points)
        
        # Create initial permutation
        perm = list(alphabet)
        random.shuffle(perm)
        
        # Set fixed points
        for pos in fixed_positions:
            current_char = perm[pos]
            target_char = alphabet[pos]
            
            # Find the position currently mapping to the target character
            target_pos = perm.index(target_char)
            
            # Swap the mappings
            perm[pos], perm[target_pos] = perm[target_pos], perm[pos]
        
        return perm
    
    def _create_reflector(self, self_loops=6):
        """
        Build a reflector (σ) that is still an involution but now **allows a
        controlled number of self-loops**.  A self-loop means σ(x) = x.
        
        Args
        ----
        self_loops : int
            How many contacts (0-25) should map to themselves.  
            • 0  → classic “no fixed points” Enigma reflector                 │  
            • 1-13 → mixed design (recommended: 4-10 to kill Bombe crib check)│  
            • 26 → σ becomes the identity (not useful; whole machine ≈ no-op)
        
        Returns
        -------
        list[str]
            A length-26 list where `mapping[i]` is the letter that contact i
            connects to.  Guaranteed to be an involution (σ = σ⁻¹).
        """
        # ---- 1.  Randomise contact indices --------------------------------
        indices = list(range(26))         # 0 … 25  represent A … Z
        random.shuffle(indices)           # Fisher-Yates
    
        # ---- 2.  Choose which indices will be self-loops -------------------
        loop_set = set(indices[:self_loops])   # first m indices → σ(x)=x
    
        # ---- 3.  Prepare output table --------------------------------------
        mapping = [''] * 26
    
        # ---- 4.  Pair up the remaining (non-loop) contacts -----------------
        free = [i for i in indices[self_loops:]]   # contacts still to wire
        while free:
            i = free.pop()     # take one free contact
            j = free.pop()     # take another
            # connect them **symmetrically**: σ(i)=j and σ(j)=i
            mapping[i] = alphabet[j]
            mapping[j] = alphabet[i]
    
        # ---- 5.  Wire each self-loop contact to itself ---------------------
        for i in loop_set:
            mapping[i] = alphabet[i]       # σ(i) = i
    
        # ---- 6.  Sanity check: σ must be an involution ---------------------
        assert all(mapping[alphabet.index(mapping[i])] == alphabet[i]
                   for i in range(26)), "Reflector is not an involution!"
    
        return mapping
    
    def rotate_rotors(self):
        """Rotate rotors (standard Enigma stepping mechanism)"""
        # Rotor1 rotates every character
        self.rotor1.position = (self.rotor1.position + 1) % len(alphabet)
        
        # When rotor1 completes a full rotation, rotor2 rotates
        if self.rotor1.position == 0:
            self.rotor2.position = (self.rotor2.position + 1) % len(alphabet)
            
            # When rotor2 completes a full rotation, rotor3 rotates
            if self.rotor2.position == 0:
                self.rotor3.position = (self.rotor3.position + 1) % len(alphabet)
                
                # When rotor3 completes a full rotation, rotor4 rotates
                if self.rotor3.position == 0:
                    self.rotor4.position = (self.rotor4.position + 1) % len(alphabet)
    
    def encrypt(self, plaintext):
        """Encrypt plaintext"""
        return self._process(plaintext.upper())
    
    def decrypt(self, ciphertext):
        """Decrypt ciphertext"""
        self.reset_positions()  # Reset rotors before decrypting
        return self._process(ciphertext.upper())
    
    def _process(self, text):
        """Process text (encryption/decryption)"""
        result = []
        for char in text:
            if char not in alphabet:
                result.append(char)
                continue
            
            # Rotate rotors before processing each character
            self.rotate_rotors()
            
            # Forward pass through all rotors
            char = self.rotor1.map_forward(char)
            char = self.rotor2.map_forward(char)
            char = self.rotor3.map_forward(char)
            char = self.rotor4.map_forward(char)
            
            # Pass through reflector
            char = alphabet[self.reflector.index(char)]
            
            # Backward pass through all rotors
            char = self.rotor4.map_backward(char)
            char = self.rotor3.map_backward(char)
            char = self.rotor2.map_backward(char)
            char = self.rotor1.map_backward(char)
            
            result.append(char)
        
        return ''.join(result)
    
    class Rotor:
        """Rotor class"""
        def __init__(self, mapping, rotor_type):
            self.mapping = mapping  # Mapping relationships
            self.inverse_mapping = self._create_inverse_mapping()  # Inverse mapping
            self.position = 0  # Current position
            self.rotor_type = rotor_type  # Rotor type
        
        def _create_inverse_mapping(self):
            """Create inverse mapping table"""
            inverse = [''] * len(alphabet)
            for i, char in enumerate(self.mapping):
                inverse[alphabet.index(char)] = alphabet[i]
            return inverse
        
        def map_forward(self, char):
            """Forward mapping (right-to-left)"""
            idx = alphabet.index(char)
            mapped_idx = (alphabet.index(
                self.mapping[(idx + self.position) % len(alphabet)]
            ) - self.position)
            return alphabet[mapped_idx % len(alphabet)]

        def map_backward(self, char):
            """Backward mapping (left-to-right)"""
            idx = alphabet.index(char)
            mapped_idx = (alphabet.index(
                self.inverse_mapping[(idx + self.position) % len(alphabet)]
            ) - self.position)
            return alphabet[mapped_idx % len(alphabet)]
        
        def __str__(self):
            """Rotor information"""
            return f"{self.rotor_type} Rotor (position={alphabet[self.position]})"
    
    def __str__(self):
        """Return machine status information"""
        rotor_info = "\n".join([
            f"Rotor 1: {self.rotor1}",
            f"Rotor 2: {self.rotor2}",
            f"Rotor 3: {self.rotor3}",
            f"Rotor 4: {self.rotor4}",
            f"Reflector: {''.join(self.reflector)}"
        ])
        return f"Enhanced Enigma Machine (Key: {self.key})\n{rotor_info}"

class EnhancedEnigmaWithPlugboard(EnhancedEnigma):
    """
    Enhanced Enigma Machine with optional plugboard layer.
    - plug_pair_count: number of plugboard connections (0 ≤ p ≤ 13)
    - plug_configuration_function: optional callback to specify exact letter pairs
    """
    def __init__(
        self,
        key: str,
        plug_pair_count: int = 0,
        plug_configuration_function: Callable[[int, str], List[Tuple[str, str]]] = None
    ) -> None:
        super().__init__(key)
        self.plugboard_mapping: Dict[str, str] = self._create_plugboard_mapping(
            plug_pair_count,
            plug_configuration_function
        )

    def _create_plugboard_mapping(
        self,
        plug_pair_count: int,
        configuration_function: Callable[[int, str], List[Tuple[str, str]]]
    ) -> Dict[str, str]:
        """
        Build the plugboard mapping.
        - Default: identity mapping (each letter maps to itself) ∀x: π(x)=x
        - If configuration_function provided, use it to obtain connection pairs
        - Otherwise, select plug_pair_count random disjoint pairs
        """
        
        if plug_pair_count < 0 or plug_pair_count > 12:
            plug_pair_count = 7
        
        # Initialize identity mapping — every letter maps to itself ∀x: π(x)=x
        mapping: Dict[str, str] = {letter: letter for letter in alphabet}

        # Determine letter pairs for swapping
        if configuration_function is not None:
            connection_pairs = configuration_function(plug_pair_count, alphabet)
        else:
            shuffled = list(alphabet)
            random.shuffle(shuffled)
            connection_pairs = [
                (shuffled[i * 2], shuffled[i * 2 + 1])
                for i in range(plug_pair_count)
            ]

        # Apply each swap — swap(a,b): π(a)=b and π(b)=a
        for a, b in connection_pairs:
            mapping[a], mapping[b] = b, a

        return mapping

    def _process(self, text: str) -> str:
        """
        Encrypt or decrypt a string through plugboard, rotors, reflector, and back.
        1) Initial plugboard swap — apply π₁
        2) Rotor and reflector pass — apply R_forward ∘ σ ∘ R_backward
        3) Final plugboard swap — apply π₁ again
        """
        output: List[str] = []

        for symbol in text:
            if symbol not in alphabet:
                output.append(symbol)
                continue

            # Step 1: initial plugboard mapping — char ← π₁(char)
            char = self.plugboard_mapping[symbol]

            # Step 2: rotor/reflector operations
            self.rotate_rotors()
            # Forward through rotors: char ← R₄(R₃(R₂(R₁(char))))
            for rotor in (self.rotor1, self.rotor2, self.rotor3, self.rotor4):
                char = rotor.map_forward(char)
            # Reflector: c ← σ(c)
            char = alphabet[self.reflector.index(char)]
            # Backward through rotors: char ← R₁⁻¹(R₂⁻¹(R₃⁻¹(R₄⁻¹(char))))
            for rotor in (self.rotor4, self.rotor3, self.rotor2, self.rotor1):
                char = rotor.map_backward(char)

            # Step 3: final plugboard mapping — char ← π₁(c)
            char = self.plugboard_mapping[char]
            output.append(char)

        return "".join(output)

def print_full_mapping(enigma):
    """Print full component mappings"""
    print("\n" + "="*60)
    print("Full Component Mappings")
    print("="*60)
    
    # Rotor 1 mapping
    print("\nRotor 1 Mapping (Derangement):")
    print("  " + ' '.join(alphabet))
    print("  " + ' '.join(enigma.rotor1.mapping))
    
    # Rotor 2 mapping
    print("\nRotor 2 Mapping (Partial Derangement):")
    print("  " + ' '.join(alphabet))
    print("  " + ' '.join(enigma.rotor2.mapping))
    
    # Rotor 3 mapping
    print("\nRotor 3 Mapping (Derangement):")
    print("  " + ' '.join(alphabet))
    print("  " + ' '.join(enigma.rotor3.mapping))
    
    # Rotor 4 mapping
    print("\nRotor 4 Mapping (Partial Derangement):")
    print("  " + ' '.join(alphabet))
    print("  " + ' '.join(enigma.rotor4.mapping))
    
    # Reflector mapping
    print("\nReflector Mapping:")
    print("  " + ' '.join(alphabet))
    print("  " + ' '.join(enigma.reflector))
    
    # Mark fixed points
    print("\nFixed Points:")
    for i, rotor in enumerate([enigma.rotor1, enigma.rotor2, enigma.rotor3, enigma.rotor4]):
        fixed_points = [alphabet[j] for j in range(len(alphabet)) if rotor.mapping[j] == alphabet[j]]
        print(f"  Rotor {i+1}: {', '.join(fixed_points)}")
    
    print("="*60)


def validate_components(enigma):
    """Validate Enigma machine components"""
    print("\nValidate Components:")
    
    # Validate rotor1 (Derangement)
    rotor1 = enigma.rotor1
    fixed_points1 = sum(1 for i, c in enumerate(alphabet) if rotor1.mapping[i] == c)
    print(f"Rotor 1: {rotor1.rotor_type}, Fixed Points: {fixed_points1} (expected 0)")
    
    # Validate rotor2 (Partial Derangement)
    rotor2 = enigma.rotor2
    fixed_points2 = sum(1 for i, c in enumerate(alphabet) if rotor2.mapping[i] == c)
    print(f"Rotor 2: {rotor2.rotor_type}, Fixed Points: {fixed_points2} (expected 10)")
    
    # Validate rotor3 (Derangement)
    rotor3 = enigma.rotor3
    fixed_points3 = sum(1 for i, c in enumerate(alphabet) if rotor3.mapping[i] == c)
    print(f"Rotor 3: {rotor3.rotor_type}, Fixed Points: {fixed_points3} (expected 0)")
    
    # Validate rotor4 (Partial Derangement)
    rotor4 = enigma.rotor4
    fixed_points4 = sum(1 for i, c in enumerate(alphabet) if rotor4.mapping[i] == c)
    print(f"Rotor 4: {rotor4.rotor_type}, Fixed Points: {fixed_points4} (expected 8)")
    
    # Validate reflector
    reflector = enigma.reflector
    valid_reflector = True
    for i in range(len(reflector)):
        char = reflector[i]
        mapped_back = reflector[alphabet.index(char)]
        if mapped_back != alphabet[i]:
            valid_reflector = False
            break
    print(f"Reflector: {'Valid involution' if valid_reflector else 'Invalid permutation'}")
    
    print(f"Initial Positions: {''.join(alphabet[p] for p in enigma.positions)}")


if __name__ == "__main__":
    # Initialize the Enigma machine with the key
    key = "MySecretKey123!"
    print(f"Initializing Enigma machine with key: {key}")
    enigma = EnhancedEnigma(key)
    
    # Print machine configuration
    print("\nMachine Configuration:")
    print(enigma)
    
    # Print full mappings
    print_full_mapping(enigma)
    
    # Validate components
    validate_components(enigma)
    
    # Encrypt plaintext
    plaintext = "ENHANCED ENIGMA MACHINE SECURITY"
    print(f"\nPlaintext: {plaintext}")
    encrypted = enigma.encrypt(plaintext)
    
    # Decrypt ciphertext (reset rotors before decrypting)
    print(f"Ciphertext: {encrypted}")
    decrypted = enigma.decrypt(encrypted)
    
    # Display results
    print("\nEncryption/Decryption Results:")
    print(f"Original: {plaintext}")
    print(f"Encrypted: {encrypted}")
    print(f"Decrypted: {decrypted}")
    print(f"Match: {''.join(plaintext.split()) == ''.join(decrypted.split())}")
    
    test_key = "MathCodePlugbard2025"
    # Configure 6 plugboard pairs
    enigma = EnhancedEnigmaWithPlugboard(test_key, plug_pair_count=6)
    plaintext = "THE QUICK BROWN FOX JUMPS OVER THE LAZY DOG"
    ciphertext = enigma.encrypt(plaintext)
    recovered = enigma.decrypt(ciphertext)

    print("\nEncryption/Decryption Results (Use plugboard):")
    print(f"Plaintext : {plaintext}")
    print(f"Ciphertext: {ciphertext}")
    print(f"Recovered : {recovered}")
    assert recovered == plaintext, "Decryption failed: recovered text does not match plaintext."