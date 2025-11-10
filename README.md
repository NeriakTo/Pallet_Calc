# Pallet Calculator

產品材積及棧板堆疊計算工具。

## 功能

- 根據產品訂單、外箱尺寸與棧板尺寸計算所需棧板數量。
- 支援設定餘數是否允許混裝堆疊。
- 輸出含棧板與不含棧板的材積（CBM 與 CUFT）。

## 安裝

專案使用 Python 3.10+，建議於虛擬環境中安裝。

```bash
pip install -r requirements.txt  # 若有額外依賴
```

（目前程式僅依賴標準程式庫，因此可直接執行。）

## 使用方式

1. 準備一份 JSON 格式的輸入檔案，例如 `example.json`：

   ```json
   {
     "products": [
       {
         "name": "999-00031",
         "order_quantity_pcs": 800,
         "pcs_per_carton": 10,
         "carton_dimensions_cm": [56, 26, 20]
       },
       {
         "name": "999-00166",
         "order_quantity_pcs": 580,
         "pcs_per_carton": 10,
         "carton_dimensions_cm": [97, 26, 20]
       }
     ],
     "pallet_dimensions_cm": {
       "length_cm": 120,
       "width_cm": 105,
       "height_cm": 195,
       "base_height_cm": 15
     },
     "allow_mixed_remainders": true,
     "container_height": "20CY"
   }
   ```

   - `products`：產品資料，可放入多個產品。
   - `order_quantity_pcs`：訂單總數（件）。
   - `pcs_per_carton`：每箱入數。
   - `carton_dimensions_cm`：外箱長、寬、高（公分）。
   - `pallet_dimensions_cm`：棧板長、寬、總高（公分）。`base_height_cm` 選填，預設 15 公分。
   - `allow_mixed_remainders`：餘數是否允許混裝堆疊（布林值）。
   - `container_height`：裝櫃高度限制，可選 `20CY`、`40CY` 或 `40HQ`。

2. 執行命令：

   ```bash
   python -m pallet_calc.cli example.json
   ```

   也可以使用 `-` 從標準輸入讀取 JSON。

3. 結果會顯示各產品最佳擺放方式、所需棧板數量、棧板拆分以及含棧板／不含棧板材積。

## 輸出說明

- **Per-product summary**：各產品的最佳擺放方向、每層箱數、每棧板層數、完整棧板與餘數。
- **Pallet breakdown**：棧板明細，包含單棧板裝載高度與每個產品的箱數。
- **Total volume**：分別列出含棧板與不含棧板的材積，單位為 CBM 與 CUFT。

## 假設與限制

- 程式假設外箱皆可沿棧板長、寬方向旋轉 90 度後擺放。
- 若允許混裝，程式會以「層」為單位將餘數堆疊於同一棧板，單層仍採用單一產品的最佳擺放方式。
- 棧板高度與貨櫃高度的最小值，扣除棧板底座高度後為可用堆疊高度。
- 目前不考慮特殊排佈（例如交錯排放）與重量限制。

## 測試

```bash
pytest
```

## 網頁介面

專案也提供簡易的網頁介面，可讓使用者在瀏覽器中輸入資料並查看計算結果：

```bash
export FLASK_APP=pallet_calc.web
flask run --reload
```

預設會在 `http://127.0.0.1:5000/` 提供表單，填寫產品訂單數量、外箱尺寸、棧板尺寸、是否允許混裝以及貨櫃高度限制後即可送出。

