#include <iostream>
#include <vector>
#include <string>
#include <algorithm>
#include <numeric>
#include <random>
#include <unordered_set>
#include <unordered_map>
#include <sstream>
#include <iomanip>
#include <cstdint>
#include <cstring>
#include <cctype>

// Enhanced Enigma Machine in C++ with manual SHA-256 implementation
static const std::string ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";

// SHA-256 implementation without external dependencies
class SHA256 {
public:
    static std::string hash(const std::string& input) {
        // Initialize hash values
        uint32_t h0 = 0x6a09e667;
        uint32_t h1 = 0xbb67ae85;
        uint32_t h2 = 0x3c6ef372;
        uint32_t h3 = 0xa54ff53a;
        uint32_t h4 = 0x510e527f;
        uint32_t h5 = 0x9b05688c;
        uint32_t h6 = 0x1f83d9ab;
        uint32_t h7 = 0x5be0cd19;

        // Pre-processing
        std::vector<uint8_t> data(input.begin(), input.end());
        uint64_t bit_len = data.size() * 8;
        data.push_back(0x80);
        while ((data.size() * 8) % 512 != 448) {
            data.push_back(0x00);
        }
        for (int i = 0; i < 8; i++) {
            data.push_back(static_cast<uint8_t>((bit_len >> (56 - i * 8)) & 0xFF));
        }

        // Process each 512-bit block
        for (size_t i = 0; i < data.size(); i += 64) {
            std::vector<uint32_t> w(64, 0);

            // Break block into 16 words
            for (int t = 0; t < 16; t++) {
                w[t] = (data[i + t*4] << 24) | 
                       (data[i + t*4 + 1] << 16) | 
                       (data[i + t*4 + 2] << 8) | 
                       (data[i + t*4 + 3]);
            }

            // Extend the first 16 words
            for (int t = 16; t < 64; t++) {
                w[t] = sigma1(w[t-2]) + w[t-7] + sigma0(w[t-15]) + w[t-16];
            }

            // Initialize working variables
            uint32_t a = h0;
            uint32_t b = h1;
            uint32_t c = h2;
            uint32_t d = h3;
            uint32_t e = h4;
            uint32_t f = h5;
            uint32_t g = h6;
            uint32_t h = h7;

            // Compression function main loop
            for (int t = 0; t < 64; t++) {
                uint32_t T1 = h + Sigma1(e) + Ch(e, f, g) + k[t] + w[t];
                uint32_t T2 = Sigma0(a) + Maj(a, b, c);
                h = g;
                g = f;
                f = e;
                e = d + T1;
                d = c;
                c = b;
                b = a;
                a = T1 + T2;
            }

            // Update hash values
            h0 += a;
            h1 += b;
            h2 += c;
            h3 += d;
            h4 += e;
            h5 += f;
            h6 += g;
            h7 += h;
        }

        // Produce final hash
        std::ostringstream result;
        result << std::hex << std::setfill('0');
        result << std::setw(8) << h0;
        result << std::setw(8) << h1;
        result << std::setw(8) << h2;
        result << std::setw(8) << h3;
        result << std::setw(8) << h4;
        result << std::setw(8) << h5;
        result << std::setw(8) << h6;
        result << std::setw(8) << h7;

        return result.str();
    }

private:
    static const uint32_t k[64];

    static uint32_t Ch(uint32_t x, uint32_t y, uint32_t z) {
        return (x & y) ^ (~x & z);
    }

    static uint32_t Maj(uint32_t x, uint32_t y, uint32_t z) {
        return (x & y) ^ (x & z) ^ (y & z);
    }

    static uint32_t Sigma0(uint32_t x) {
        return rotr(x, 2) ^ rotr(x, 13) ^ rotr(x, 22);
    }

    static uint32_t Sigma1(uint32_t x) {
        return rotr(x, 6) ^ rotr(x, 11) ^ rotr(x, 25);
    }

    static uint32_t sigma0(uint32_t x) {
        return rotr(x, 7) ^ rotr(x, 18) ^ (x >> 3);
    }

    static uint32_t sigma1(uint32_t x) {
        return rotr(x, 17) ^ rotr(x, 19) ^ (x >> 10);
    }

    static uint32_t rotr(uint32_t x, int n) {
        return (x >> n) | (x << (32 - n));
    }
};

// SHA-256 constants
const uint32_t SHA256::k[64] = {
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
};

// 大整数类
class BigInt {
public:
    std::vector<uint32_t> digits;
    static const uint32_t BASE = (uint32_t)0x100000000; // 2^32

    BigInt() {}
    
    BigInt(uint64_t n) {
        if (n == 0) {
            digits.push_back(0);
        } else {
            digits.push_back(static_cast<uint32_t>(n & 0xFFFFFFFF));
            if (n > 0xFFFFFFFF) {
                digits.push_back(static_cast<uint32_t>(n >> 32));
            }
        }
    }
    
    // 从十六进制字符串创建大整数
    BigInt(const std::string& hexStr) {
        for (char c : hexStr) {
            *this = this->multiply(16);
            *this = this->add(hexCharToInt(c));
        }
    }
    
    // 转换为32位整数（取模2^32）
    uint32_t toUint32() const {
        if (digits.empty()) return 0;
        return digits[0];
    }
    
    // 加法
    BigInt add(uint32_t n) const {
        BigInt result = *this;
        uint64_t carry = n;
        
        for (size_t i = 0; i < result.digits.size(); i++) {
            uint64_t sum = static_cast<uint64_t>(result.digits[i]) + carry;
            result.digits[i] = static_cast<uint32_t>(sum & 0xFFFFFFFF);
            carry = sum >> 32;
        }
        
        if (carry > 0) {
            result.digits.push_back(static_cast<uint32_t>(carry));
        }
        
        return result;
    }
    
    // 乘法
    BigInt multiply(uint32_t n) const {
        BigInt result;
        uint64_t carry = 0;
        
        for (uint32_t digit : digits) {
            uint64_t product = static_cast<uint64_t>(digit) * n + carry;
            result.digits.push_back(static_cast<uint32_t>(product & 0xFFFFFFFF));
            carry = product >> 32;
        }
        
        if (carry > 0) {
            result.digits.push_back(static_cast<uint32_t>(carry));
        }
        
        // 移除前导零
        while (!result.digits.empty() && result.digits.back() == 0) {
            result.digits.pop_back();
        }
        
        // 确保至少有一个零
        if (result.digits.empty()) {
            result.digits.push_back(0);
        }
        
        return result;
    }
    
private:
    static uint8_t hexCharToInt(char c) {
        if (c >= '0' && c <= '9') return c - '0';
        if (c >= 'a' && c <= 'f') return c - 'a' + 10;
        if (c >= 'A' && c <= 'F') return c - 'A' + 10;
        return 0;
    }
};

// Generate seed exactly like Python: take full SHA-256 hex digest as big integer mod 2^32
uint32_t generateSeed(const std::string &key) {
    std::string hash_val = SHA256::hash(key);
    // 使用大整数类精确计算
    BigInt bigIntHash(hash_val);
    uint32_t seed = bigIntHash.toUint32();
    
    return seed;
}

// MT19937 implementation
class MT19937 {
public:
    MT19937(uint32_t seed) {
        index = N;
        mt[0] = seed;
        for (int i = 1; i < N; i++) {
            mt[i] = (1812433253UL * (mt[i-1] ^ (mt[i-1] >> 30)) + i);
            mt[i] &= 0xFFFFFFFFUL;
        }
    }

    uint32_t extract() {
        if (index >= N) {
            twist();
        }
        uint32_t y = mt[index];
        y ^= (y >> 11);
        y ^= ((y << 7) & 0x9D2C5680UL);
        y ^= ((y << 15) & 0xEFC60000UL);
        y ^= (y >> 18);
        index++;
        return y & 0xFFFFFFFFUL;
    }

    int rand_int(int lo, int hi) {
        if (hi < lo) std::swap(lo, hi);
        uint32_t range = static_cast<uint32_t>(hi - lo + 1);
        return lo + static_cast<int>(extract() % range);
    }

    template <typename T>
    void shuffle(std::vector<T>& vec) {
        int n = vec.size();
        for (int i = n-1; i > 0; i--) {
            int j = rand_int(0, i);
            std::swap(vec[i], vec[j]);
        }
    }

    template <typename T>
    std::vector<T> sample(const std::vector<T>& vec, int k) {
        std::vector<T> temp = vec;
        shuffle(temp);
        if (k > temp.size()) k = temp.size();
        return std::vector<T>(temp.begin(), temp.begin() + k);
    }

private:
    static const int N = 624;
    static const int M = 397;
    static const uint32_t A = 0x9908B0DFUL;
    static const uint32_t UPPER = 0x80000000UL;
    static const uint32_t LOWER = 0x7FFFFFFFUL;

    uint32_t mt[N];
    int index;

    void twist() {
        for (int i = 0; i < N; i++) {
            uint32_t x = (mt[i] & UPPER) | (mt[(i+1) % N] & LOWER);
            uint32_t xA = x >> 1;
            if (x & 1) {
                xA ^= A;
            }
            mt[i] = mt[(i + M) % N] ^ xA;
        }
        index = 0;
    }
};

class Rotor {
public:
    std::vector<char> mapping;
    std::vector<char> inverse_mapping;
    int position;
    std::string rotor_type;
    Rotor(const std::vector<char> &map, const std::string &type)
        : mapping(map), rotor_type(type), position(0) {
        inverse_mapping.resize(ALPHABET.size());
        for (size_t i = 0; i < mapping.size(); ++i)
            inverse_mapping[ALPHABET.find(mapping[i])] = ALPHABET[i];
    }
    char mapForward(char c) {
        int idx = ALPHABET.find(c);
        int mapped = ALPHABET.find(mapping[(idx + position) % ALPHABET.size()]);
        return ALPHABET[(mapped - position + ALPHABET.size()) % ALPHABET.size()];
    }
    char mapBackward(char c) {
        int idx = ALPHABET.find(c);
        int mapped = ALPHABET.find(inverse_mapping[(idx + position) % ALPHABET.size()]);
        return ALPHABET[(mapped - position + ALPHABET.size()) % ALPHABET.size()];
    }
    std::string toString() const {
        return rotor_type + " Rotor (pos=" + std::string(1, ALPHABET[position]) + ")";
    }
};

class EnhancedEnigma {
public:
    EnhancedEnigma(const std::string &key)
        : key(key), seed(generateSeed(key)), rng(seed) {
        rotors.push_back(createRotor(true));
        rotors.push_back(createRotor(false, 10));
        rotors.push_back(createRotor(true));
        rotors.push_back(createRotor(false, 7));
        reflector = createReflector(6);
        positions = derivePositions(key, 4);
        resetPositions();
    }
    std::string encrypt(const std::string &pt) { return process(pt); }
    std::string decrypt(const std::string &ct) { resetPositions(); return process(ct); }
    std::string toString() const {
        std::ostringstream oss;
        oss << "Enhanced Enigma Machine (Key: " << key << ")\n";
        for (size_t i = 0; i < rotors.size(); ++i)
            oss << "Rotor " << i+1 << ": " << rotors[i].toString() << "\n";
        oss << "Reflector: "; for (char c : reflector) oss << c; oss << "\n";
        return oss.str();
    }
protected:
    std::string key;
    uint32_t seed;
    MT19937 rng;
    std::vector<Rotor> rotors;
    std::vector<char> reflector;
    std::vector<int> positions;
    Rotor createRotor(bool derange, int fixed_pointes = 0) {
        if (derange) return Rotor(generate_derangement(), "Derangement");
        return Rotor(generate_partial_derangement(fixed_pointes), "Partial Derangement (fixed="+std::to_string(fixed_pts)+")");
    }
    std::vector<char> generate_derangement() {
        while (true) {
            std::vector<char> perm;
            for (char c : ALPHABET) perm.push_back(c);
            rng.shuffle(perm);
            bool valid = true;
            for (int i = 0; i < perm.size(); i++) {
                if (perm[i] == ALPHABET[i]) {
                    valid = false;
                    break;
                }
            }
            if (valid) return perm;
        }
    }

    std::vector<char> generate_partial_derangement(int fixed_points) {
        const int n = ALPHABET.size();
        // 限制 fixed_points 在合理区间
        fixed_points = std::clamp(fixed_points, 1, n - 2);

        // 1. 随机选定 k 个固定点位置
        std::vector<int> indices(n);
        std::iota(indices.begin(), indices.end(), 0);
        std::vector<int> fixed_positions = rng.sample(indices, fixed_points);
        std::unordered_set<int> fixed_set(fixed_positions.begin(), fixed_positions.end());

        // 2. 准备结果列表，初始化为占位
        std::vector<char> perm(n);

        // 3. 对固定点位置，直接赋值
        for (int pos : fixed_positions) {
            perm[pos] = ALPHABET[pos];
        }

        // 4. 处理剩下的位置：做一个无固定点排列
        std::vector<int> other_positions;
        other_positions.reserve(n - fixed_points);
        for (int i = 0; i < n; ++i) {
            if (!fixed_set.count(i)) {
                other_positions.push_back(i);
            }
        }
        std::vector<char> other_chars;
        other_chars.reserve(other_positions.size());
        for (int pos : other_positions) {
            other_chars.push_back(ALPHABET[pos]);
        }

        // 随机生成一个完全无固定点排列
        bool ok = false;
        while (!ok) {
            rng.shuffle(other_chars);
            ok = true;
            for (size_t i = 0; i < other_positions.size(); ++i) {
                if (other_chars[i] == ALPHABET[other_positions[i]]) {
                    ok = false;
                    break;
                }
            }
        }

        // 5. 填回结果
        for (size_t i = 0; i < other_positions.size(); ++i) {
            perm[other_positions[i]] = other_chars[i];
        }

        return perm;
    }
    std::vector<char> createReflector(int loops) {
        std::vector<int> idx(26); std::iota(idx.begin(), idx.end(), 0);
        rng.shuffle(idx);
        std::unordered_set<int> loopset(idx.begin(), idx.begin()+loops);
        std::vector<char> map(26);
        std::vector<int> freeidx(idx.begin()+loops, idx.end());
        while (freeidx.size()>1) {
            int i = freeidx.back(); freeidx.pop_back();
            int j = freeidx.back(); freeidx.pop_back();
            map[i]=ALPHABET[j]; map[j]=ALPHABET[i];
        }
        for (int i:loopset) map[i] = ALPHABET[i];
        return map;
    }
    std::vector<int> derivePositions(const std::string &k, int count) {
        std::vector<int> pos;
        std::string h = SHA256::hash(k);
        for (int i = 0; i < count*2 && i+1 < (int)h.size(); i+=2)
            pos.push_back(std::stoul(h.substr(i,2),nullptr,16)%ALPHABET.size());
        while ((int)pos.size()<count)
            pos.push_back(0);
        return pos;
    }
    void resetPositions() { for (size_t i=0;i<rotors.size();++i) rotors[i].position=positions[i]; }
    
    // 与Python一致的转子旋转逻辑
    void rotateRotors() {
        for (size_t i = 0; i < rotors.size(); i++) {
            rotors[i].position = (rotors[i].position + 1) % ALPHABET.size();
            if (rotors[i].position != 0) {
                break; // 只旋转到第一个未归零的转子
            }
        }
    }
    std::string process(const std::string &txt) {
        std::string res;
        for (char c:txt) {
            if (ALPHABET.find(c)==std::string::npos) {res.push_back(c); continue;}
            rotateRotors(); char ch=c;
            for (auto &r:rotors) ch=r.mapForward(ch);
            ch=reflector[ALPHABET.find(ch)];
            for (auto it=rotors.rbegin();it!=rotors.rend();++it) ch=it->mapBackward(ch);
            res.push_back(ch);
        }
        return res;
    }
};

class EnhancedEnigmaWithPlugboard : public EnhancedEnigma {
public:
    EnhancedEnigmaWithPlugboard(const std::string &k,int p=0):EnhancedEnigma(k){createPlugboard(p);}    
    std::string encrypt(const std::string &t){return processWithPlugboard(t);}  
    std::string decrypt(const std::string &t){resetPositions();return processWithPlugboard(t);}  
private:
    std::unordered_map<char,char> plugboard;
    void createPlugboard(int cnt){
        if(cnt<0||cnt>13)cnt=7;
        std::vector<char> letters(ALPHABET.begin(),ALPHABET.end());
        rng.shuffle(letters);
        for(char c:ALPHABET) plugboard[c]=c;
        for(int i=0;i<cnt;++i){char a=letters[2*i],b=letters[2*i+1];plugboard[a]=b;plugboard[b]=a;}}
    std::string processWithPlugboard(const std::string &txt){
        std::string out;
        for(char c:txt){
            if(ALPHABET.find(c)==std::string::npos){out.push_back(c);continue;}
            char ch=plugboard[c];rotateRotors();for(auto&r:rotors) ch=r.mapForward(ch);
            ch=reflector[ALPHABET.find(ch)];for(auto it=rotors.rbegin();it!=rotors.rend();++it) ch=it->mapBackward(ch);
            ch=plugboard[ch];out.push_back(ch);
        }
        return out;
    }
};

int main(){
    std::string key="MySecretKey123!";
    std::cout<<"Initializing Enigma machine with key: "<<key<<"\n";
    EnhancedEnigma enigma(key);
    std::cout<<"\nMachine Configuration:\n"<<enigma.toString()<<"\n";
    std::string plaintext="ENHANCED ENIGMA MACHINE SECURITY";
    std::string ciphertext=enigma.encrypt(plaintext);
    std::string recovered=enigma.decrypt(ciphertext);
    std::cout<<"Plaintext: "<<plaintext<<"\n";
    std::cout<<"Ciphertext: "<<ciphertext<<"\n";
    std::cout<<"Decrypted: "<<recovered<<"\n";
    std::cout<<"Match: "<<std::boolalpha<<(plaintext==recovered)<<"\n";
    std::string test_key="MathCodePlugbard2025";
    EnhancedEnigmaWithPlugboard enigma2(test_key,6);
    std::string sample="THE QUICK BROWN FOX JUMPS OVER THE LAZY DOG";
    std::string enc2=enigma2.encrypt(sample);
    std::string dec2=enigma2.decrypt(enc2);
    std::cout<<"\nWith Plugboard:\n";
    std::cout<<"Plaintext : "<<sample<<"\n";
    std::cout<<"Ciphertext: "<<enc2<<"\n";
    std::cout<<"Decrypted : "<<dec2<<"\n";
    return 0;
}