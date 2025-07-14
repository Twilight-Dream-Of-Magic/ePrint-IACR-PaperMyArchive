# iwt_core 擴展加載說明

## 若出現「DLL load failed: 找不到指定的模块」

`iwt_core.*.pyd` 若用 **Clang/LLVM** 編譯，會依賴：

- **libc++.dll**
- **libunwind.dll**

這兩者不會隨 Windows 或 VC++ Redist 安裝，需由**本目錄**或 **PATH** 提供。

### 做法一：複製 DLL 到本目錄（推薦）

從你用來編譯 iwt_core 的 Clang/LLVM 的 `bin` 目錄複製到 **本目錄**（`iwt_research/native/`）：

- `libc++.dll`
- `libunwind.dll`

常見路徑示例：

- VS 內建 Clang：`C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Tools\Llvm\bin\`
- 或：`C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Tools\Llvm\x64\bin\`
- 獨立 LLVM：`C:\Program Files\LLVM\bin\`

複製後在專案根目錄執行：

```cmd
set PYTHONPATH=%CD%
py -3.14 -m iwt_research.tests.test_iwt_core
```

### 做法二：用 MSVC 重新編譯（不依賴 Clang DLL）

在 **Developer Command Prompt for VS 2022** 中，確保使用 MSVC 而非 Clang 編譯 iwt_core，則生成的 .pyd 只依賴 VC++ Redist，無需 libc++.dll/libunwind.dll。例如：

```cmd
cd iwt_research\iwt_core
cmake -B build -G "Visual Studio 17 2022" -A x64
cmake --build build
```

（若 CMake 預設選了 Clang，可在 CMake 配置時指定 `-DCMAKE_CXX_COMPILER=cl` 使用 MSVC。）

### 做法三：Clang 靜態連結 libc++（需有靜態庫）

Clang **可以**靜態編譯，但需有 **靜態版** 的 libc++ 與 libunwind（多數 LLVM/VS 安裝只帶 DLL 與 import lib）。若你已自建或取得靜態的 `libc++.lib`、`libunwind.lib`，可：

```cmd
cd iwt_research\iwt_core
cmake -B build -DIWT_LLVM_LIB_DIR=路徑\含\靜態\lib 的目錄
cmake --build build
```

CMake 會嘗試從編譯器路徑或常見 VS/LLVM 路徑自動尋找該目錄；若該目錄裡是 DLL 的 import lib 而非靜態庫，連結後仍會依賴 libc++.dll。要真正靜態需使用 MSVC 編譯（做法二）或自行從 LLVM 源碼建出靜態 libc++。
