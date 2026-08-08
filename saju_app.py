import datetime
import tkinter as tk
from tkinter import ttk, messagebox

# 음력 변환 라이브러리 확인
try:
    from korean_lunar_calendar import KoreanLunarCalendar
    HAS_LUNAR_LIB = True
except ImportError:
    HAS_LUNAR_LIB = False

# 1. 천간과 지지 데이터
HEAVENLY_STEMS = ["갑", "을", "병", "정", "무", "기", "경", "신", "임", "계"]
EARTHLY_BRANCHES = ["자", "축", "인", "묘", "진", "사", "오", "미", "신", "유", "술", "해"]

# 2. 음력 -> 양력 변환 함수
def convert_lunar_to_solar(year, month, day, is_leap_month=False):
    if not HAS_LUNAR_LIB:
        return None
    calendar = KoreanLunarCalendar()
    calendar.setLunarDate(year, month, day, is_leap_month)
    return calendar.solarYear, calendar.solarMonth, calendar.solarDay

# 3. 정밀 사주 계산 로직
def get_precise_saju(year, month, day, hour, is_lunar=False, is_leap_month=False):
    if is_lunar:
        if not HAS_LUNAR_LIB:
            return {"error": "korean-lunar-calendar 라이브러리가 필요합니다."}
        solar_y, solar_m, solar_d = convert_lunar_to_solar(year, month, day, is_leap_month)
    else:
        solar_y, solar_m, solar_d = year, month, day

    target_date = datetime.date(solar_y, solar_m, solar_d)

    # 연주 계산 (입춘 2월 4일 기준)
    saju_year = solar_y
    if (solar_m < 2) or (solar_m == 2 and solar_d < 4):
        saju_year -= 1

    year_stem_idx = (saju_year - 4) % 10
    year_branch_idx = (saju_year - 4) % 12

    # 월주 계산 (절기 기준)
    if (solar_m == 2 and solar_d >= 4) or (solar_m == 3 and solar_d < 6):
        saju_month_idx = 0
    elif (solar_m == 3 and solar_d >= 6) or (solar_m == 4 and solar_d < 5):
        saju_month_idx = 1
    elif (solar_m == 4 and solar_d >= 5) or (solar_m == 5 and solar_d < 6):
        saju_month_idx = 2
    elif (solar_m == 5 and solar_d >= 6) or (solar_m == 6 and solar_d < 6):
        saju_month_idx = 3
    elif (solar_m == 6 and solar_d >= 6) or (solar_m == 7 and solar_d < 7):
        saju_month_idx = 4
    elif (solar_m == 7 and solar_d >= 7) or (solar_m == 8 and solar_d < 7):
        saju_month_idx = 5
    elif (solar_m == 8 and solar_d >= 7) or (solar_m == 9 and solar_d < 8):
        saju_month_idx = 6
    elif (solar_m == 9 and solar_d >= 8) or (solar_m == 10 and solar_d < 8):
        saju_month_idx = 7
    elif (solar_m == 10 and solar_d >= 8) or (solar_m == 11 and solar_d < 7):
        saju_month_idx = 8
    elif (solar_m == 11 and solar_d >= 7) or (solar_m == 12 and solar_d < 7):
        saju_month_idx = 9
    elif (solar_m == 12 and solar_d >= 7) or (solar_m == 1 and solar_d < 6):
        saju_month_idx = 10
    else:
        saju_month_idx = 11

    month_branch_idx = (saju_month_idx + 2) % 12
    month_stem_idx = ((year_stem_idx % 5) * 2 + 2 + saju_month_idx) % 10

    # 일주 계산 (1900-01-01 기준)
    base_date = datetime.date(1900, 1, 1)
    diff_days = (target_date - base_date).days
    if hour >= 23:
        diff_days += 1

    day_stem_idx = (diff_days + 0) % 10
    day_branch_idx = (diff_days + 10) % 12

    # 시주 계산
    hour_branch_idx = ((hour + 1) % 24) // 2
    hour_stem_idx = ((day_stem_idx % 5) * 2 + hour_branch_idx) % 10

    return {
        "solar_date": f"{solar_y}년 {solar_m}월 {solar_d}일 {hour}시",
        "year": f"{HEAVENLY_STEMS[year_stem_idx]}{EARTHLY_BRANCHES[year_branch_idx]}",
        "month": f"{HEAVENLY_STEMS[month_stem_idx]}{EARTHLY_BRANCHES[month_branch_idx]}",
        "day": f"{HEAVENLY_STEMS[day_stem_idx]}{EARTHLY_BRANCHES[day_branch_idx]}",
        "hour": f"{HEAVENLY_STEMS[hour_stem_idx]}{EARTHLY_BRANCHES[hour_branch_idx]}"
    }

# 4. GUI 애플리케이션 클래스 정의
class SajuApp:
    def __init__(self, root):
        self.root = root
        self.root.title("만세력 사주팔자 계산기")
        self.root.geometry("450x520")
        self.root.resizable(False, False)

        # 스타일 설정
        style = ttk.Style()
        style.theme_use("clam")

        # 메인 프레임
        main_frame = ttk.Frame(root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 제목
        title_label = ttk.Label(main_frame, text="🔮 사주팔자 계산기", font=("맑은 고딕", 16, "bold"))
        title_label.pack(pady=(0, 15))

        # 입력 영역 프레임
        input_frame = ttk.LabelFrame(main_frame, text=" 생년월일시 입력 ", padding="15")
        input_frame.pack(fill=tk.X, pady=(0, 15))

        # 날짜/시간 입력 필드
        ttk.Label(input_frame, text="연도 (YYYY):").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.entry_year = ttk.Entry(input_frame, width=12)
        self.entry_year.insert(0, "1962")
        self.entry_year.grid(row=0, column=1, sticky=tk.W, pady=5)

        ttk.Label(input_frame, text="월 (MM):").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.entry_month = ttk.Entry(input_frame, width=12)
        self.entry_month.insert(0, "1")
        self.entry_month.grid(row=1, column=1, sticky=tk.W, pady=5)

        ttk.Label(input_frame, text="일 (DD):").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.entry_day = ttk.Entry(input_frame, width=12)
        self.entry_day.insert(0, "28")
        self.entry_day.grid(row=2, column=1, sticky=tk.W, pady=5)

        ttk.Label(input_frame, text="시 (0~23시):").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.entry_hour = ttk.Entry(input_frame, width=12)
        self.entry_hour.insert(0, "10")
        self.entry_hour.grid(row=3, column=1, sticky=tk.W, pady=5)

        # 음력 / 윤달 체크박스
        self.var_lunar = tk.BooleanVar(value=False)
        self.var_leap = tk.BooleanVar(value=False)

        chk_lunar = ttk.Checkbutton(input_frame, text="음력", variable=self.var_lunar)
        chk_lunar.grid(row=4, column=0, sticky=tk.W, pady=5)

        chk_leap = ttk.Checkbutton(input_frame, text="윤달(음력 전용)", variable=self.var_leap)
        chk_leap.grid(row=4, column=1, sticky=tk.W, pady=5)

        # 계산 버튼
        calc_btn = ttk.Button(main_frame, text="사주팔자 조회", command=self.calculate)
        calc_btn.pack(fill=tk.X, ipady=5, pady=(0, 15))

        # 결과 표시 프레임
        result_frame = ttk.LabelFrame(main_frame, text=" 조회 결과 ", padding="15")
        result_frame.pack(fill=tk.BOTH, expand=True)

        self.lbl_solar = ttk.Label(result_frame, text="양력 기준: -", font=("맑은 고딕", 9))
        self.lbl_solar.pack(anchor=tk.W, pady=(0, 10))

        # 사주 표기 레이블 (시주, 일주, 월주, 연주)
        saju_grid = ttk.Frame(result_frame)
        saju_grid.pack(fill=tk.X)

        headers = ["시주(時柱)", "일주(日柱)", "월주(月柱)", "연주(年柱)"]
        for idx, text in enumerate(headers):
            lbl = ttk.Label(saju_grid, text=text, font=("맑은 고딕", 10, "bold"))
            lbl.grid(row=0, column=idx, padx=10, pady=5)

        self.res_hour = ttk.Label(saju_grid, text="-", font=("맑은 고딕", 12), foreground="blue")
        self.res_hour.grid(row=1, column=0, padx=10)

        self.res_day = ttk.Label(saju_grid, text="-", font=("맑은 고딕", 12), foreground="blue")
        self.res_day.grid(row=1, column=1, padx=10)

        self.res_month = ttk.Label(saju_grid, text="-", font=("맑은 고딕", 12), foreground="blue")
        self.res_month.grid(row=1, column=2, padx=10)

        self.res_year = ttk.Label(saju_grid, text="-", font=("맑은 고딕", 12), foreground="blue")
        self.res_year.grid(row=1, column=3, padx=10)

    def calculate(self):
        try:
            y = int(self.entry_year.get())
            m = int(self.entry_month.get())
            d = int(self.entry_day.get())
            h = int(self.entry_hour.get())

            if not (1900 <= y <= 2100) or not (1 <= m <= 12) or not (1 <= d <= 31) or not (0 <= h <= 23):
                messagebox.showerror("입력 오류", "날짜 및 시간 범위를 올바르게 입력해 주세요.")
                return

            res = get_precise_saju(y, m, d, h, self.var_lunar.get(), self.var_leap.get())

            if "error" in res:
                messagebox.showerror("오류", res["error"])
                return

            self.lbl_solar.config(text=f"양력 기준: {res['solar_date']}")
            self.res_hour.config(text=res["hour"])
            self.res_day.config(text=res["day"])
            self.res_month.config(text=res["month"])
            self.res_year.config(text=res["year"])

        except ValueError:
            messagebox.showerror("입력 오류", "숫자만 정확하게 입력해 주세요.")

if __name__ == "__main__":
    root = tk.Tk()
    app = SajuApp(root)
    root.mainloop()