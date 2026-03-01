"""
Amazon product data + profit estimation for demo.
Uses realistic mock product catalogue + real HTS tariff lookup.
"""
from __future__ import annotations

import random
from datetime import date, timedelta
from typing import Any

_TODAY = date(2026, 2, 24)


def _gen_history(base: float, days: int = 30) -> list[dict[str, Any]]:
    result = []
    price = base
    for i in range(days, -1, -1):
        delta = random.uniform(-0.03, 0.03)
        price = round(max(base * 0.85, min(base * 1.15, price * (1 + delta))), 2)
        result.append({"date": (_TODAY - timedelta(days=i)).isoformat(), "price": price})
    return result


def _gen_bsr_history(base: int, days: int = 30) -> list[dict[str, Any]]:
    result = []
    bsr = base
    for i in range(days, -1, -1):
        delta = random.uniform(-0.05, 0.05)
        bsr = max(1, int(bsr * (1 + delta)))
        result.append({"date": (_TODAY - timedelta(days=i)).isoformat(), "bsr": bsr})
    return result


_CATALOGUE: list[dict[str, Any]] = [
    {"asin":"B08N5WRWNW","title":"Gaiam Essentials Premium Yoga Mat","brand":"Gaiam","category":"Sports & Outdoors","image":"https://m.media-amazon.com/images/I/71pHMaKnYCL._AC_SX679_.jpg","price":24.98,"rating":4.5,"review_count":48320,"bsr":142,"weight_lbs":2.2,"dimensions_inches":[24.0,4.0,4.0],"hts_code":"9506910020","cog_usd":4.50},
    {"asin":"B07VGRFBDS","title":"YETI Rambler 20 oz Tumbler Stainless Steel","brand":"YETI","category":"Kitchen & Dining","image":"https://m.media-amazon.com/images/I/61X9bSEHqQL._AC_SX679_.jpg","price":35.00,"rating":4.8,"review_count":92410,"bsr":58,"weight_lbs":0.88,"dimensions_inches":[3.5,3.5,6.9],"hts_code":"7323930060","cog_usd":6.80},
    {"asin":"B09G9FPHY6","title":"Govee LED Strip Lights 100ft Smart WiFi RGB","brand":"Govee","category":"Tools & Home Improvement","image":"https://m.media-amazon.com/images/I/71U1szLfJSL._AC_SX679_.jpg","price":39.99,"rating":4.3,"review_count":31870,"bsr":213,"weight_lbs":1.1,"dimensions_inches":[8.0,4.0,3.0],"hts_code":"9405490000","cog_usd":7.20},
    {"asin":"B08F7N3JQ7","title":"Anker PowerCore 26800 Portable Charger","brand":"Anker","category":"Electronics","image":"https://m.media-amazon.com/images/I/61GfUwBOhFL._AC_SX679_.jpg","price":55.99,"rating":4.7,"review_count":64200,"bsr":89,"weight_lbs":1.3,"dimensions_inches":[6.5,3.0,1.0],"hts_code":"8507600020","cog_usd":11.50},
    {"asin":"B093BVYZQB","title":"Resistance Bands Set 5 Exercise Bands for Working Out","brand":"FitBeast","category":"Sports & Outdoors","image":"https://m.media-amazon.com/images/I/71mSKJcjJ-L._AC_SX679_.jpg","price":18.99,"rating":4.4,"review_count":27650,"bsr":398,"weight_lbs":0.55,"dimensions_inches":[7.0,5.0,2.0],"hts_code":"9506910030","cog_usd":2.80},
    {"asin":"B07PXGQC1Q","title":"Instant Pot Duo 7-in-1 Electric Pressure Cooker 6 Qt","brand":"Instant Pot","category":"Kitchen & Dining","image":"https://m.media-amazon.com/images/I/71WtwEvYDOS._AC_SX679_.jpg","price":99.95,"rating":4.7,"review_count":145320,"bsr":12,"weight_lbs":11.8,"dimensions_inches":[13.4,12.2,12.5],"hts_code":"8516606000","cog_usd":22.00},
    {"asin":"B08HLQP5Q9","title":"Silicone Stretch Lids Set of 14 Reusable Bowl Covers","brand":"Kitcheon","category":"Kitchen & Dining","image":"https://m.media-amazon.com/images/I/71PvtpJcpRL._AC_SX679_.jpg","price":15.99,"rating":4.6,"review_count":21480,"bsr":521,"weight_lbs":0.35,"dimensions_inches":[8.0,8.0,3.0],"hts_code":"3924102000","cog_usd":2.50},
    {"asin":"B08Y8NXGKJ","title":"Laptop Stand Adjustable Aluminum Ergonomic Holder","brand":"Nulaxy","category":"Electronics","image":"https://m.media-amazon.com/images/I/61RcXa5NRPL._AC_SX679_.jpg","price":29.99,"rating":4.5,"review_count":38920,"bsr":276,"weight_lbs":1.76,"dimensions_inches":[10.2,8.5,1.5],"hts_code":"8473302000","cog_usd":5.50},
    {"asin":"B0CXRWMWYZ","title":"Remote Control Car for Kids 1:16 Scale High Speed RC Toy Car 4WD","brand":"BEZGAR","category":"Toys & Games","image":"https://m.media-amazon.com/images/I/71wOUThNsXL._AC_SX679_.jpg","price":39.99,"rating":4.4,"review_count":12850,"bsr":334,"weight_lbs":2.1,"dimensions_inches":[14.0,10.0,6.5],"hts_code":"9503000013","cog_usd":7.50},
    # Extra products for trending / category pages
    {"asin":"B07FQ4TRCR","title":"Ninja AF101 Air Fryer 4 Qt Compact","brand":"Ninja","category":"Kitchen & Dining","image":"https://m.media-amazon.com/images/I/71nY4DCxYEL._AC_SX679_.jpg","price":99.95,"rating":4.8,"review_count":122400,"bsr":8,"weight_lbs":11.7,"dimensions_inches":[13.0,11.8,11.8],"hts_code":"8516609000","cog_usd":24.00},
    {"asin":"B095JJDMTD","title":"JLab Go Air Pop True Wireless Earbuds","brand":"JLab","category":"Electronics","image":"https://m.media-amazon.com/images/I/61rPGNLAuJL._AC_SX679_.jpg","price":19.99,"rating":4.2,"review_count":55100,"bsr":67,"weight_lbs":0.07,"dimensions_inches":[2.5,2.0,1.5],"hts_code":"8518300000","cog_usd":4.80},
    {"asin":"B009JKRFVK","title":"TriggerPoint GRID Foam Roller 13-inch Dense Core","brand":"TriggerPoint","category":"Sports & Outdoors","image":"https://m.media-amazon.com/images/I/71cq6VtUqDL._AC_SX679_.jpg","price":36.99,"rating":4.7,"review_count":41200,"bsr":180,"weight_lbs":1.14,"dimensions_inches":[13.0,5.5,5.5],"hts_code":"9506990000","cog_usd":5.80},
    {"asin":"B0B8HJVFHM","title":"TaoTronics LED Desk Lamp USB Charging Port Eye-Caring","brand":"TaoTronics","category":"Tools & Home Improvement","image":"https://m.media-amazon.com/images/I/61DLZV8LmHL._AC_SX679_.jpg","price":25.99,"rating":4.5,"review_count":18340,"bsr":420,"weight_lbs":1.87,"dimensions_inches":[5.0,5.0,17.0],"hts_code":"9405100000","cog_usd":5.20},
    {"asin":"B08C4Q3G2B","title":"Optimum Nutrition Gold Standard 100% Whey Protein Powder 5 lb","brand":"Optimum Nutrition","category":"Health & Household","image":"https://m.media-amazon.com/images/I/81A0bx2FPEL._AC_SX679_.jpg","price":74.99,"rating":4.7,"review_count":83200,"bsr":3,"weight_lbs":5.18,"dimensions_inches":[8.9,7.0,7.0],"hts_code":"2106909998","cog_usd":22.00},
    {"asin":"B01N5IB20Q","title":"Hydro Flask Water Bottle 32 oz Wide Mouth Insulated","brand":"Hydro Flask","category":"Sports & Outdoors","image":"https://m.media-amazon.com/images/I/61C8JN3fZDL._AC_SX679_.jpg","price":44.95,"rating":4.8,"review_count":76500,"bsr":95,"weight_lbs":0.94,"dimensions_inches":[3.8,3.8,9.2],"hts_code":"7323930000","cog_usd":9.50},
    {"asin":"B01MQWUXZS","title":"Fit Simplify Resistance Loop Exercise Bands Set of 5","brand":"Fit Simplify","category":"Sports & Outdoors","image":"https://m.media-amazon.com/images/I/71J8QG8XJYL._AC_SX679_.jpg","price":9.99,"rating":4.6,"review_count":67800,"bsr":52,"weight_lbs":0.12,"dimensions_inches":[9.0,9.0,1.5],"hts_code":"9506910030","cog_usd":1.20},
    {"asin":"B08KTZ8249","title":"Cable Management Box Large Cord Organizer for Office","brand":"D-Line","category":"Electronics","image":"https://m.media-amazon.com/images/I/71e0JT9YtHL._AC_SX679_.jpg","price":22.99,"rating":4.5,"review_count":14560,"bsr":612,"weight_lbs":0.8,"dimensions_inches":[14.0,5.0,4.0],"hts_code":"3926909990","cog_usd":3.50},

    # ── Children's Clothing ────────────────────────────────────────────────────
    {"asin":"B09QGSL3MT","title":"Carter's Baby Girls' 4-Piece Fleece Pajama Set","brand":"Carter's","category":"Children's Clothing","image":"https://m.media-amazon.com/images/I/81t3PKxEF3L._AC_SX679_.jpg","price":22.00,"rating":4.7,"review_count":18430,"bsr":210,"weight_lbs":0.6,"dimensions_inches":[10.0,8.0,2.0],"hts_code":"6111206010","cog_usd":3.60},
    {"asin":"B07PNBJ3R8","title":"Simple Joys by Carter's Baby 6-Pack Short-Sleeve Bodysuit","brand":"Simple Joys","category":"Children's Clothing","image":"https://m.media-amazon.com/images/I/91Q4VCpUo9L._AC_SX679_.jpg","price":19.60,"rating":4.8,"review_count":62100,"bsr":34,"weight_lbs":0.45,"dimensions_inches":[9.0,7.0,1.5],"hts_code":"6111206010","cog_usd":3.00},
    {"asin":"B08T8Y4WV7","title":"Nike Boys' Classic Fleece Hoodie Pullover Sweatshirt","brand":"Nike","category":"Children's Clothing","image":"https://m.media-amazon.com/images/I/71X4WnH6a0L._AC_SX679_.jpg","price":40.00,"rating":4.6,"review_count":9820,"bsr":380,"weight_lbs":0.9,"dimensions_inches":[12.0,10.0,2.0],"hts_code":"6110203020","cog_usd":7.50},
    {"asin":"B07F1NJQXK","title":"Columbia Boys' Watertight Rain Jacket","brand":"Columbia","category":"Children's Clothing","image":"https://m.media-amazon.com/images/I/71F2P6FGFNL._AC_SX679_.jpg","price":55.00,"rating":4.5,"review_count":7640,"bsr":520,"weight_lbs":0.75,"dimensions_inches":[12.0,8.0,2.5],"hts_code":"6201922030","cog_usd":10.50},
    {"asin":"B09X3V8MT4","title":"Gerber Baby Girls' 4-Pack Long-Sleeve Onesies Bodysuits","brand":"Gerber","category":"Children's Clothing","image":"https://m.media-amazon.com/images/I/81RhFLnRwdL._AC_SX679_.jpg","price":16.99,"rating":4.7,"review_count":24500,"bsr":155,"weight_lbs":0.4,"dimensions_inches":[8.0,6.0,1.5],"hts_code":"6111206010","cog_usd":2.80},
    {"asin":"B08KQWV5N3","title":"OshKosh B'Gosh Boys Stretchable Classic Denim Jeans","brand":"OshKosh B'Gosh","category":"Children's Clothing","image":"https://m.media-amazon.com/images/I/71hf-d3bYtL._AC_SX679_.jpg","price":26.99,"rating":4.4,"review_count":11200,"bsr":430,"weight_lbs":0.7,"dimensions_inches":[12.0,9.0,1.5],"hts_code":"6203422011","cog_usd":5.20},
    {"asin":"B07V1J92MX","title":"Under Armour Boys' Tech Short Sleeve T-Shirt","brand":"Under Armour","category":"Children's Clothing","image":"https://m.media-amazon.com/images/I/61OkFTJ+PyL._AC_SX679_.jpg","price":20.00,"rating":4.6,"review_count":15800,"bsr":290,"weight_lbs":0.35,"dimensions_inches":[10.0,8.0,1.0],"hts_code":"6109100012","cog_usd":3.50},
    {"asin":"B09V7KXQP4","title":"Hanna Andersson Kids Organic Cotton Zip Hoodie","brand":"Hanna Andersson","category":"Children's Clothing","image":"https://m.media-amazon.com/images/I/71Dmo9NJSBL._AC_SX679_.jpg","price":48.00,"rating":4.8,"review_count":5320,"bsr":610,"weight_lbs":0.8,"dimensions_inches":[11.0,9.0,2.0],"hts_code":"6110203020","cog_usd":9.20},
    {"asin":"B07Q4HMJQP","title":"Luvable Friends Baby Unisex 20-Pack Socks Newborn","brand":"Luvable Friends","category":"Children's Clothing","image":"https://m.media-amazon.com/images/I/81BFBJcmj-L._AC_SX679_.jpg","price":12.99,"rating":4.6,"review_count":38900,"bsr":88,"weight_lbs":0.25,"dimensions_inches":[6.0,5.0,2.0],"hts_code":"6111206010","cog_usd":1.80},
    {"asin":"B08NWMJ4QY","title":"Puma Boys' Essential Logo Jogger Pants","brand":"Puma","category":"Children's Clothing","image":"https://m.media-amazon.com/images/I/71n4KF7MGQL._AC_SX679_.jpg","price":28.00,"rating":4.5,"review_count":8760,"bsr":470,"weight_lbs":0.55,"dimensions_inches":[11.0,8.0,1.5],"hts_code":"6103430010","cog_usd":5.00},

    # ── Beauty & Personal Care ─────────────────────────────────────────────────
    {"asin":"B00TTD9BRC","title":"CeraVe Moisturizing Cream 16 oz Daily Face and Body Moisturizer","brand":"CeraVe","category":"Beauty & Personal Care","image":"https://m.media-amazon.com/images/I/61S8A4DcIEL._AC_SX679_.jpg","price":19.99,"rating":4.8,"review_count":189400,"bsr":5,"weight_lbs":1.3,"dimensions_inches":[4.5,3.5,5.0],"hts_code":"3304990050","cog_usd":3.80},
    {"asin":"B00BDZL6HE","title":"L'Oreal Paris Voluminous Original Mascara Washable Black","brand":"L'Oreal Paris","category":"Beauty & Personal Care","image":"https://m.media-amazon.com/images/I/61QBB8iANPL._AC_SX679_.jpg","price":9.99,"rating":4.5,"review_count":72300,"bsr":42,"weight_lbs":0.15,"dimensions_inches":[1.5,1.5,5.5],"hts_code":"3303000010","cog_usd":1.50},
    {"asin":"B07DDQL4HR","title":"e.l.f. Poreless Putty Primer Vegan Face Primer","brand":"e.l.f. Cosmetics","category":"Beauty & Personal Care","image":"https://m.media-amazon.com/images/I/61ViKcDsVDL._AC_SX679_.jpg","price":11.99,"rating":4.4,"review_count":95600,"bsr":28,"weight_lbs":0.18,"dimensions_inches":[2.0,2.0,3.5],"hts_code":"3304990050","cog_usd":1.90},
    {"asin":"B00AQ6XA52","title":"Neutrogena Hydro Boost Water Gel Face Moisturizer 1.7 oz","brand":"Neutrogena","category":"Beauty & Personal Care","image":"https://m.media-amazon.com/images/I/61GNlQpJdSL._AC_SX679_.jpg","price":18.99,"rating":4.5,"review_count":43800,"bsr":65,"weight_lbs":0.3,"dimensions_inches":[2.5,2.5,4.0],"hts_code":"3304990050","cog_usd":3.50},
    {"asin":"B07W4VXGD4","title":"The Ordinary Niacinamide 10% + Zinc 1% 30ml","brand":"The Ordinary","category":"Beauty & Personal Care","image":"https://m.media-amazon.com/images/I/51YWkQADk8L._AC_SX679_.jpg","price":9.90,"rating":4.5,"review_count":87200,"bsr":17,"weight_lbs":0.12,"dimensions_inches":[1.5,1.5,4.0],"hts_code":"3304990050","cog_usd":1.40},
    {"asin":"B07C7SZLDM","title":"OGX Extra Strength Damage Remedy + Coconut Miracle Oil Shampoo 25.4 fl oz","brand":"OGX","category":"Beauty & Personal Care","image":"https://m.media-amazon.com/images/I/81HBlTDPe0L._AC_SX679_.jpg","price":11.47,"rating":4.7,"review_count":52100,"bsr":38,"weight_lbs":1.9,"dimensions_inches":[3.5,2.5,8.5],"hts_code":"3305100000","cog_usd":2.20},
    {"asin":"B00B2JT5TI","title":"Maybelline Fit Me Matte + Poreless Foundation 30ml Soft Beige","brand":"Maybelline","category":"Beauty & Personal Care","image":"https://m.media-amazon.com/images/I/61DRWQ17b9L._AC_SX679_.jpg","price":9.98,"rating":4.4,"review_count":48700,"bsr":55,"weight_lbs":0.2,"dimensions_inches":[1.5,1.5,4.5],"hts_code":"3304990050","cog_usd":1.60},
    {"asin":"B07K3F7XCY","title":"Real Techniques Miracle Complexion Sponge 2-Pack Makeup Blender","brand":"Real Techniques","category":"Beauty & Personal Care","image":"https://m.media-amazon.com/images/I/61h4q3-K4TL._AC_SX679_.jpg","price":11.59,"rating":4.6,"review_count":35400,"bsr":96,"weight_lbs":0.08,"dimensions_inches":[4.0,3.0,1.5],"hts_code":"3307900050","cog_usd":1.60},
    {"asin":"B004Y5FVLW","title":"Revlon ColorStay Lip Liner Pencil with Built-in Sharpener","brand":"Revlon","category":"Beauty & Personal Care","image":"https://m.media-amazon.com/images/I/61X45Z8WDDL._AC_SX679_.jpg","price":7.99,"rating":4.5,"review_count":28900,"bsr":130,"weight_lbs":0.06,"dimensions_inches":[0.5,0.5,6.5],"hts_code":"3304100000","cog_usd":1.10},
    {"asin":"B01LX3L7QJ","title":"NYX Professional Makeup Epic Ink Liner Waterproof Felt Tip","brand":"NYX Professional Makeup","category":"Beauty & Personal Care","image":"https://m.media-amazon.com/images/I/51tGBOqeqWL._AC_SX679_.jpg","price":10.00,"rating":4.3,"review_count":41500,"bsr":108,"weight_lbs":0.08,"dimensions_inches":[0.5,0.5,6.0],"hts_code":"3303000010","cog_usd":1.50},

    # ── Automotive ─────────────────────────────────────────────────────────────
    {"asin":"B07CRPFZGS","title":"Chemical Guys HOL169 16-Piece Complete Car Wash Kit","brand":"Chemical Guys","category":"Automotive","image":"https://m.media-amazon.com/images/I/91YcEJl1z+L._AC_SX679_.jpg","price":79.99,"rating":4.7,"review_count":14200,"bsr":185,"weight_lbs":8.5,"dimensions_inches":[16.0,12.0,14.0],"hts_code":"3405200000","cog_usd":16.00},
    {"asin":"B00BL3ZFDG","title":"Meguiar's G17516 Ultimate Quick Detailer 15.2 fl oz","brand":"Meguiar's","category":"Automotive","image":"https://m.media-amazon.com/images/I/71nAnzGY9zL._AC_SX679_.jpg","price":15.84,"rating":4.8,"review_count":31700,"bsr":76,"weight_lbs":1.2,"dimensions_inches":[3.5,3.5,9.0],"hts_code":"3405200000","cog_usd":2.80},
    {"asin":"B005K67D1C","title":"SYLVANIA H11 SilverStar Ultra Headlight Bulb 2-Pack High Performance","brand":"SYLVANIA","category":"Automotive","image":"https://m.media-amazon.com/images/I/61G4qiKYS8L._AC_SX679_.jpg","price":28.99,"rating":4.4,"review_count":22800,"bsr":242,"weight_lbs":0.35,"dimensions_inches":[7.0,4.0,3.0],"hts_code":"8539211000","cog_usd":5.50},
    {"asin":"B000FV3TL4","title":"Rain-X Latitude 2-n-1 Water Repellency Wiper Blade 22-inch","brand":"Rain-X","category":"Automotive","image":"https://m.media-amazon.com/images/I/71gRjMZTPAL._AC_SX679_.jpg","price":18.99,"rating":4.5,"review_count":19600,"bsr":318,"weight_lbs":0.5,"dimensions_inches":[24.0,3.0,2.0],"hts_code":"8512209000","cog_usd":3.80},
    {"asin":"B00AR3HQSS","title":"WD-40 Multi-Use Product Smart Straw 12 oz","brand":"WD-40","category":"Automotive","image":"https://m.media-amazon.com/images/I/61MJi3HCDWL._AC_SX679_.jpg","price":10.97,"rating":4.8,"review_count":78400,"bsr":22,"weight_lbs":0.95,"dimensions_inches":[3.0,2.5,9.0],"hts_code":"3403990000","cog_usd":1.80},
    {"asin":"B01M6ZDBS2","title":"ACDelco Gold 41-993 Professional Iridium Spark Plug (4-Pack)","brand":"ACDelco","category":"Automotive","image":"https://m.media-amazon.com/images/I/71cFGsNq4FL._AC_SX679_.jpg","price":28.00,"rating":4.7,"review_count":11900,"bsr":390,"weight_lbs":0.3,"dimensions_inches":[6.0,3.0,2.0],"hts_code":"8511100010","cog_usd":6.00},
    {"asin":"B005IHT94S","title":"Armor All Interior Car Cleaner Spray Bottle 16 fl oz","brand":"Armor All","category":"Automotive","image":"https://m.media-amazon.com/images/I/71PkxQbTHSL._AC_SX679_.jpg","price":7.98,"rating":4.5,"review_count":24300,"bsr":145,"weight_lbs":1.3,"dimensions_inches":[3.5,3.0,9.5],"hts_code":"3405200000","cog_usd":1.40},
    {"asin":"B07CWBN7D8","title":"Chemical Guys Big Mouth Max Flow Foam Cannon","brand":"Chemical Guys","category":"Automotive","image":"https://m.media-amazon.com/images/I/71jjfCyQqcL._AC_SX679_.jpg","price":49.99,"rating":4.4,"review_count":8700,"bsr":560,"weight_lbs":1.8,"dimensions_inches":[10.0,5.0,8.0],"hts_code":"8424200000","cog_usd":9.50},
    {"asin":"B0072QXGY0","title":"Bosch 26A ICON Wiper Blade 26-inch Driver Side","brand":"Bosch","category":"Automotive","image":"https://m.media-amazon.com/images/I/71NI-YMp7-L._AC_SX679_.jpg","price":19.97,"rating":4.7,"review_count":42600,"bsr":112,"weight_lbs":0.55,"dimensions_inches":[28.0,3.5,2.5],"hts_code":"8512209000","cog_usd":3.80},
    {"asin":"B08K4LSJ3F","title":"Turtle Wax 50734 Complete Car Care Kit 10-Piece","brand":"Turtle Wax","category":"Automotive","image":"https://m.media-amazon.com/images/I/81TqjnFAtSL._AC_SX679_.jpg","price":35.99,"rating":4.5,"review_count":16800,"bsr":280,"weight_lbs":5.2,"dimensions_inches":[14.0,10.0,8.0],"hts_code":"3405200000","cog_usd":7.00},
]

_PRODUCTS: dict[str, dict[str, Any]] = {}
for _p in _CATALOGUE:
    _p["price_history"] = _gen_history(_p["price"])
    _p["bsr_history"] = _gen_bsr_history(_p["bsr"])
    _PRODUCTS[_p["asin"]] = _p


def estimate_fba_fee(weight_lbs: float, dims_inches: list[float]) -> float:
    l, w, h = sorted(dims_inches, reverse=True)
    if weight_lbs <= 1 and l <= 15 and w <= 12 and h <= 0.75:
        return round(3.06 + max(0, weight_lbs - 0.5) * 0.32, 2)
    elif weight_lbs <= 20 and l <= 18 and w <= 14 and h <= 8:
        if weight_lbs <= 1:
            return 3.68
        elif weight_lbs <= 2:
            return 4.75
        elif weight_lbs <= 3:
            return 5.40
        else:
            return round(5.40 + (weight_lbs - 3) * 0.38, 2)
    else:
        return round(9.61 + weight_lbs * 0.38, 2)


def estimate_referral_fee(price: float, category: str) -> float:
    rates = {"Electronics": 0.08, "Sports & Outdoors": 0.15,
             "Kitchen & Dining": 0.15, "Tools & Home Improvement": 0.15,
             "Toys & Games": 0.15, "Children's Clothing": 0.17,
             "Beauty & Personal Care": 0.15, "Automotive": 0.12}
    return round(price * rates.get(category, 0.15), 2)


def estimate_shipping_cost(weight_lbs: float) -> float:
    return round(max(0.8, weight_lbs * 0.453592 * 1.8), 2)


def search_products(keyword: str) -> list[dict[str, Any]]:
    kw = keyword.lower().strip()
    if not kw:
        return [_summary(p) for p in _PRODUCTS.values()]
    return [_summary(p) for p in _PRODUCTS.values()
            if kw in p["title"].lower() or kw in p["brand"].lower() or kw in p["category"].lower()]


def get_product(asin: str) -> dict[str, Any] | None:
    return _PRODUCTS.get(asin)


_CUSTOMS_BROKER_FEE = 150.0   # per entry
_CUSTOMS_ISF_FEE = 35.0       # ISF 10+2 filing
_CUSTOMS_BOND_FEE = 12.0      # single-entry bond
_CUSTOMS_EXAM_PROB = 0.03     # 3% chance of exam
_CUSTOMS_EXAM_COST = 500.0    # average exam cost
_DEFAULT_UNITS_PER_SHIPMENT = 100


def calculate_profit(
    asin: str,
    tariff_rate: float = 0.0,
    include_customs: bool = True,
    units_per_shipment: int = _DEFAULT_UNITS_PER_SHIPMENT,
) -> dict[str, Any] | None:
    p = _PRODUCTS.get(asin)
    if not p:
        return None
    price = p["price"]
    cog = p["cog_usd"]
    fba = estimate_fba_fee(p["weight_lbs"], p["dimensions_inches"])
    referral = estimate_referral_fee(price, p["category"])
    shipping = estimate_shipping_cost(p["weight_lbs"])
    tariff_amount = round(cog * tariff_rate, 2)

    # Customs costs amortized per unit
    customs_per_unit = 0.0
    customs_detail = None
    if include_customs:
        total_customs = (
            _CUSTOMS_BROKER_FEE
            + _CUSTOMS_ISF_FEE
            + _CUSTOMS_BOND_FEE
            + _CUSTOMS_EXAM_PROB * _CUSTOMS_EXAM_COST
        )
        units = max(1, units_per_shipment)
        customs_per_unit = round(total_customs / units, 2)
        customs_detail = {
            "broker_fee_per_unit": round(_CUSTOMS_BROKER_FEE / units, 2),
            "isf_fee_per_unit": round(_CUSTOMS_ISF_FEE / units, 2),
            "bond_fee_per_unit": round(_CUSTOMS_BOND_FEE / units, 2),
            "exam_risk_per_unit": round((_CUSTOMS_EXAM_PROB * _CUSTOMS_EXAM_COST) / units, 2),
            "total_per_unit": customs_per_unit,
            "units_in_shipment": units,
        }

    total_cost = round(cog + fba + referral + shipping + tariff_amount + customs_per_unit, 2)
    net_profit = round(price - total_cost, 2)
    breakdown = {
        "cost_of_goods": cog,
        "shipping_china_us": shipping,
        "tariff": tariff_amount,
        "tariff_rate_pct": round(tariff_rate * 100, 2),
        "hts_code": p["hts_code"],
        "fba_fee": fba,
        "amazon_referral_fee": referral,
    }
    if customs_detail:
        breakdown["customs_costs"] = customs_detail
        breakdown["customs_per_unit"] = customs_per_unit
    return {
        "asin": asin,
        "title": p["title"],
        "price": price,
        "breakdown": breakdown,
        "total_cost": total_cost,
        "net_profit": net_profit,
        "margin_pct": round(net_profit / price * 100, 1) if price > 0 else 0.0,
        "roi_pct": round(net_profit / cog * 100, 1) if cog > 0 else 0.0,
    }


def get_competitor_data(asin: str) -> dict[str, Any] | None:
    p = _PRODUCTS.get(asin)
    if not p:
        return None
    return {
        "asin": asin,
        "title": p["title"],
        "current_price": p["price"],
        "current_bsr": p["bsr"],
        "rating": p["rating"],
        "review_count": p["review_count"],
        "price_history": p["price_history"],
        "bsr_history": p["bsr_history"],
        "price_low_30d": min(x["price"] for x in p["price_history"]),
        "price_high_30d": max(x["price"] for x in p["price_history"]),
    }


def _summary(p: dict[str, Any]) -> dict[str, Any]:
    return {k: p[k] for k in ("asin","title","brand","category","image","price","rating","review_count","bsr","hts_code")}


# ── Trending Products ─────────────────────────────────────────────────────────

def _trending_score(p: dict[str, Any]) -> float:
    """Higher review count + rating + low BSR = high score."""
    return p["review_count"] * p["rating"] / max(p["bsr"] ** 0.6, 1)


def _bsr_trend(p: dict[str, Any]) -> str:
    """Compare first-week avg BSR vs last-week avg BSR to get direction."""
    hist = p.get("bsr_history", [])
    if len(hist) < 14:
        return "stable"
    first_week = sum(x["bsr"] for x in hist[:7]) / 7
    last_week = sum(x["bsr"] for x in hist[-7:]) / 7
    if last_week < first_week * 0.92:
        return "up"
    if last_week > first_week * 1.08:
        return "down"
    return "stable"


def _est_monthly_revenue(p: dict[str, Any]) -> float:
    """Rough estimate: monthly sales ≈ 1000 / bsr^0.7 * 30."""
    daily_sales = 1000 / max(p["bsr"] ** 0.7, 1)
    return round(p["price"] * daily_sales * 30, 0)


def get_trending_products(category: str | None = None, limit: int = 15) -> list[dict[str, Any]]:
    prods = list(_PRODUCTS.values())
    if category and category != "All":
        prods = [p for p in prods if p["category"] == category]
    prods.sort(key=_trending_score, reverse=True)
    result = []
    for rank, p in enumerate(prods[:limit], 1):
        summary = _summary(p)
        summary["rank"] = rank
        summary["trending_score"] = round(_trending_score(p), 1)
        summary["bsr_trend"] = _bsr_trend(p)
        summary["est_monthly_revenue"] = _est_monthly_revenue(p)
        summary["est_monthly_sales"] = int(summary["est_monthly_revenue"] / p["price"])
        result.append(summary)
    return result


# ── Category Stats ────────────────────────────────────────────────────────────

# Extra market context injected for categories with few demo products
_CATEGORY_EXTRA: dict[str, dict[str, Any]] = {
    "Sports & Outdoors":     {"market_size_bn": 12.4, "yoy_growth_pct": 8.2,  "avg_tariff_pct": 4.4},
    "Kitchen & Dining":      {"market_size_bn": 9.8,  "yoy_growth_pct": 5.1,  "avg_tariff_pct": 3.1},
    "Electronics":           {"market_size_bn": 28.6, "yoy_growth_pct": 11.3, "avg_tariff_pct": 2.8},
    "Tools & Home Improvement": {"market_size_bn": 7.1,"yoy_growth_pct": 6.7, "avg_tariff_pct": 3.9},
    "Toys & Games":          {"market_size_bn": 5.3,  "yoy_growth_pct": 3.8,  "avg_tariff_pct": 0.0},
    "Health & Household":    {"market_size_bn": 18.2, "yoy_growth_pct": 14.6, "avg_tariff_pct": 2.9},
    "Children's Clothing":   {"market_size_bn": 8.6,  "yoy_growth_pct": 6.4,  "avg_tariff_pct": 15.9},
    "Beauty & Personal Care":{"market_size_bn": 22.3, "yoy_growth_pct": 16.8, "avg_tariff_pct": 0.5},
    "Automotive":            {"market_size_bn": 11.7, "yoy_growth_pct": 7.1,  "avg_tariff_pct": 2.5},
}

_COMP_LEVEL = {(1,50): "Very High", (51,200): "High", (201,500): "Medium", (501,9999): "Low"}

def _competition_label(avg_bsr: float) -> str:
    for (lo, hi), label in _COMP_LEVEL.items():
        if lo <= avg_bsr <= hi:
            return label
    return "Low"

def _opportunity_score(avg_bsr: float, avg_margin: float, yoy: float) -> int:
    score = 50
    score += min(30, (1000 / max(avg_bsr, 1)) * 3)
    score += min(15, avg_margin * 0.3)
    score += min(10, yoy * 0.5)
    return min(98, max(10, int(score)))


def get_category_stats() -> list[dict[str, Any]]:
    from collections import defaultdict
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for p in _PRODUCTS.values():
        groups[p["category"]].append(p)

    result = []
    for cat, prods in sorted(groups.items()):
        avg_price = round(sum(p["price"] for p in prods) / len(prods), 2)
        avg_rating = round(sum(p["rating"] for p in prods) / len(prods), 2)
        avg_bsr = round(sum(p["bsr"] for p in prods) / len(prods), 0)
        avg_reviews = int(sum(p["review_count"] for p in prods) / len(prods))
        # Rough margin estimate at 0% tariff
        margins = []
        for p in prods:
            cog = p["cog_usd"]
            fba = estimate_fba_fee(p["weight_lbs"], p["dimensions_inches"])
            ref = estimate_referral_fee(p["price"], p["category"])
            ship = estimate_shipping_cost(p["weight_lbs"])
            margins.append((p["price"] - cog - fba - ref - ship) / p["price"] * 100)
        avg_margin = round(sum(margins) / len(margins), 1)
        extra = _CATEGORY_EXTRA.get(cat, {"market_size_bn": 3.0, "yoy_growth_pct": 5.0, "avg_tariff_pct": 3.5})
        yoy = extra["yoy_growth_pct"]
        result.append({
            "category": cat,
            "product_count": len(prods),
            "avg_price": avg_price,
            "avg_rating": avg_rating,
            "avg_bsr": int(avg_bsr),
            "avg_review_count": avg_reviews,
            "avg_margin_pct": avg_margin,
            "competition_level": _competition_label(avg_bsr),
            "opportunity_score": _opportunity_score(avg_bsr, avg_margin, yoy),
            "market_size_bn": extra["market_size_bn"],
            "yoy_growth_pct": yoy,
            "avg_tariff_pct": extra["avg_tariff_pct"],
            "top_products": [_summary(p) for p in sorted(prods, key=lambda x: x["bsr"])[:3]],
        })
    # sort by opportunity_score desc
    result.sort(key=lambda x: x["opportunity_score"], reverse=True)
    return result


# ── Tariff & Policy News ──────────────────────────────────────────────────────

_NEWS: list[dict[str, Any]] = [
    {
        "id": "n001",
        "date": "2026-02-20",
        "title": "Section 301 Tariffs on Chinese Goods Remain in Effect; USTR Confirms No Rollback",
        "title_zh": "301条款对华关税维持不变，USTR确认无撤销计划",
        "summary": "The Office of the United States Trade Representative (USTR) confirmed that Section 301 tariffs on approximately $370 billion in Chinese imports will remain in place. Lists 1–4A continue to carry 25% additional duty on most goods; List 4B (apparel, footwear) remains at 7.5%.",
        "summary_zh": "USTR确认，针对约3700亿美元中国进口商品的301条款关税将继续维持。清单1-4A大多数商品附加25%关税；清单4B（服装、鞋类）维持7.5%。",
        "tag": "Section 301",
        "severity": "high",
        "affected_categories": ["Electronics", "Machinery", "Consumer Goods"],
        "source": "USTR",
        "source_url": "https://ustr.gov/issue-areas/enforcement/section-301-investigations",
    },
    {
        "id": "n002",
        "date": "2026-02-18",
        "title": "CBP Closes De Minimis Exemption Loophole for China-Origin Packages Below $800",
        "title_zh": "CBP关闭中国直邮包裹800美元以下免税豁免漏洞",
        "summary": "U.S. Customs and Border Protection (CBP) began enforcing the executive order that eliminated the de minimis duty-free exemption for packages originating from China and Hong Kong. All shipments, regardless of value, now face full tariff assessment. Direct-ship cross-border sellers must update landed cost models immediately.",
        "summary_zh": "美国海关执行行政命令，取消中国和香港发货包裹的800美元以下免税豁免。所有货物无论价值高低均需缴纳正式关税。直邮跨境卖家须立即更新落地成本模型。",
        "tag": "De Minimis",
        "severity": "high",
        "affected_categories": ["All Direct-Ship Categories"],
        "source": "CBP",
        "source_url": "https://www.cbp.gov/trade/trade-enforcement/tftea/de-minimis",
    },
    {
        "id": "n003",
        "date": "2026-02-12",
        "title": "HTS Chapter 85 Rate Update: Solar Cells & EV Batteries See Increased Duties",
        "title_zh": "HTS第85章税率更新：太阳能电池和电动车电池关税上调",
        "summary": "As part of the IRA and trade policy review, HTS subheadings under 8507.10 and 8541.40 covering lithium-ion batteries and solar cells have been updated. New rates effective March 1, 2026. Sellers of portable power banks and EV accessories should verify their HTS classifications.",
        "summary_zh": "根据IRA和贸易政策审议，8507.10和8541.40章节下的锂电池和太阳能电池关税已更新，自2026年3月1日起生效。便携充电宝和电动车配件卖家应核实HTS分类。",
        "tag": "HTS Update",
        "severity": "medium",
        "affected_categories": ["Electronics", "Automotive"],
        "source": "USITC",
        "source_url": "https://hts.usitc.gov",
    },
    {
        "id": "n004",
        "date": "2026-02-08",
        "title": "USD/CNY Exchange Rate Hits 7.35 Amid Fed Policy Uncertainty",
        "title_zh": "美联储政策不确定性下，美元/人民币汇率升至7.35",
        "summary": "The renminbi weakened to 7.35 against the US dollar as markets priced in the Federal Reserve maintaining higher-for-longer interest rates. For Chinese exporters pricing in USD, margin compression continues. Consider locking in forward-rate contracts if your supplier invoices in CNY.",
        "summary_zh": "由于市场预期美联储维持高利率，人民币对美元贬至7.35。对以美元报价的中国出口商而言，利润空间持续压缩。建议与供应商以人民币计价时考虑锁定远期汇率合约。",
        "tag": "FX Alert",
        "severity": "medium",
        "affected_categories": ["All China-Sourced Products"],
        "source": "Bloomberg",
        "source_url": "https://www.bloomberg.com/markets/currencies",
    },
    {
        "id": "n005",
        "date": "2026-01-30",
        "title": "FMC Announces Spot Ocean Freight Rate Surge: China–US West Coast +38%",
        "title_zh": "FMC公告：中美西海岸航线即期运费大幅上涨38%",
        "summary": "The Federal Maritime Commission (FMC) released Q1 2026 shipping data showing a 38% spike in spot freight rates on the China–US West Coast lane, driven by port congestion in Guangzhou and increased container demand. Sellers using FOB pricing should renegotiate or factor updated rates into landed cost.",
        "summary_zh": "FMC公布2026年Q1数据，受广州港拥堵及集装箱需求上升影响，中美西海岸航线即期运费飙升38%。使用FOB定价的卖家应重新谈判或将最新运费纳入落地成本。",
        "tag": "Freight Alert",
        "severity": "high",
        "affected_categories": ["All Freight Shipments"],
        "source": "FMC",
        "source_url": "https://www.fmc.gov",
    },
    {
        "id": "n006",
        "date": "2026-01-22",
        "title": "New Anti-Dumping Duties Proposed on Steel and Aluminum Products from China",
        "title_zh": "美拟对中国钢铁和铝产品征收新反倾销税",
        "summary": "The Department of Commerce initiated new anti-dumping investigations covering a range of steel and aluminum products under HTS chapters 72–76. Preliminary rates could reach 50–120%. Sellers of kitchen utensils, cookware, and structural hardware should monitor the proceeding.",
        "summary_zh": "美国商务部对HTS第72-76章下的钢铁和铝制品启动反倾销调查，初步税率可能达50%-120%。厨具、炊具和金属五金卖家应密切关注进展。",
        "tag": "Anti-Dumping",
        "severity": "medium",
        "affected_categories": ["Kitchen & Dining", "Tools & Home Improvement"],
        "source": "Commerce Dept.",
        "source_url": "https://enforcement.trade.gov/antidumping/antidumping.html",
    },
    {
        "id": "n007",
        "date": "2026-01-15",
        "title": "CPSC Issues Import Alert on Toy Products Lacking ASTM F963 Certification",
        "title_zh": "CPSC对未通过ASTM F963认证的玩具产品发布进口警告",
        "summary": "The Consumer Product Safety Commission issued a heightened import alert for toy products from Chinese suppliers lacking valid ASTM F963-17 third-party testing certificates. CBP is actively detaining shipments at Los Angeles and Long Beach ports. Ensure your toy supplier has current certificates before shipping.",
        "summary_zh": "消费品安全委员会对中国供应商无有效ASTM F963-17第三方检测证书的玩具产品发出进口警告。CBP正在洛杉矶和长滩港主动扣押货物。发货前请确保供应商持有最新证书。",
        "tag": "Compliance",
        "severity": "high",
        "affected_categories": ["Toys & Games"],
        "source": "CPSC",
        "source_url": "https://www.cpsc.gov",
    },
    {
        "id": "n008",
        "date": "2026-01-08",
        "title": "US–EU Trade Deal Negotiations Advance: Potential Tariff Cuts on Consumer Electronics",
        "title_zh": "美欧贸易协议谈判取得进展：消费电子产品关税可能下调",
        "summary": "Preliminary reporting from Geneva suggests US–EU ITA-II negotiations may include MFN tariff reductions on consumer electronics under HTS chapters 84–85. While finalization is 12–18 months away, sellers sourcing electronics from outside China may benefit. Monitoring recommended.",
        "summary_zh": "日内瓦消息称，美欧ITA-II谈判可能包括对第84-85章消费电子产品的最惠国关税削减。虽然距离最终确定仍有12-18个月，但从中国以外采购电子产品的卖家可能受益。建议持续跟踪。",
        "tag": "Trade Deal",
        "severity": "low",
        "affected_categories": ["Electronics"],
        "source": "WTO/USTR",
        "source_url": "https://ustr.gov",
    },
    {
        "id": "n009",
        "date": "2025-12-20",
        "title": "Amazon FBA Fee Changes Effective January 15, 2026: Standard Size Increases 2–5%",
        "title_zh": "亚马逊FBA费用调整自2026年1月15日起生效：标准尺寸上涨2-5%",
        "summary": "Amazon announced FBA fulfillment fee increases averaging 2.5% for standard-sized items and 4.8% for large oversize. The peak season surcharge has also been expanded from Oct–Dec to Sep–Jan. Update your profit models to reflect the new fee schedule.",
        "summary_zh": "亚马逊宣布FBA配送费平均上涨：标准尺寸约2.5%，大号超大件约4.8%。旺季附加费范围也从10-12月扩展至9月-次年1月。请更新利润模型以反映新费率。",
        "tag": "Amazon Policy",
        "severity": "medium",
        "affected_categories": ["All FBA Products"],
        "source": "Amazon Seller Central",
        "source_url": "https://sellercentral.amazon.com/help/hub/reference/G201074400",
    },
    {
        "id": "n010",
        "date": "2025-12-10",
        "title": "HTS Reclassification: Wireless Charging Accessories Moved to Chapter 85 8504",
        "title_zh": "HTS重新分类：无线充电配件调整至第85章8504税目",
        "summary": "CBP issued a ruling letter (NY N342156) reclassifying wireless charging pads and stands from HTS 8543.70 to 8504.40, which carries a higher general duty rate of 2.0% vs. Free. Sellers of wireless chargers should update HTS codes on commercial invoices immediately to avoid underpayment penalties.",
        "summary_zh": "CBP发布裁定书（NY N342156），将无线充电板和支架从8543.70重新分类至8504.40，一般税率从免税升至2.0%。无线充电器卖家应立即更新商业发票上的HTS编码，以避免欠税罚款。",
        "tag": "HTS Update",
        "severity": "medium",
        "affected_categories": ["Electronics"],
        "source": "CBP",
        "source_url": "https://rulings.cbp.gov",
    },
]


def get_tariff_news(limit: int = 20) -> list[dict[str, Any]]:
    return _NEWS[:limit]

