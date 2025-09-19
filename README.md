# Korean Equity Post-Market Research Toolkit

이 저장소는 구글 Colab 환경에서 당일(15:30 KST) 한국 주식시장 마감 데이터를
수집하여 시황을 분석하고, 다음 거래일 추가 상승이 기대되는 종목을
추천하기 위한 파이썬 파이프라인을 제공합니다.

## 주요 기능

- **마감 시황 요약**: KOSPI/KOSDAQ 지수 등락, 강세 섹터, 수급 특이 종목을
  자동으로 정리합니다.
- **경제 일정 & 미국 증시 전망**: 다음 날 발표 예정인 주요 경제지표와 미
  증시 3대 지수의 흐름을 파악합니다.
- **종목 추천**: 최근 4개 분기 EPS 양호, 이동평균선 정배열, 연속 수급,
  RSI·볼린저 밴드 기반 기술적 조건을 충족하는 종목 중 상위 10개를
  표로 제공합니다.

## Colab에서 사용 방법

1. **노트북 준비**
   - 새로운 Google Colab 노트북을 생성하고 런타임 유형을 Python 3로 설정합니다.

2. **필수 패키지 설치**
   ```python
   !pip install -q FinanceDataReader pykrx ta investpy
   ```
   > Colab 기본 런타임에는 pandas, numpy가 포함되어 있습니다. 최신 버전이
   > 필요한 경우 `!pip install -q -U pandas numpy` 를 추가로 실행하세요.

3. **소스 코드 로드**
   - 방법 A: 저장소를 직접 내려받습니다.
     ```python
     !wget -q https://raw.githubusercontent.com/<your-org>/<your-repo>/main/src/colab_stock_research.py
     import colab_stock_research as csr
     ```
     > 실제 저장소 URL로 `<your-org>/<your-repo>` 부분을 교체하세요.
   - 방법 B: 로컬에서 `src/colab_stock_research.py` 파일을 Colab으로 업로드합니다.
     ```python
     from google.colab import files
     uploaded = files.upload()
     import colab_stock_research as csr
     ```

4. **파이프라인 실행**
   ```python
   from datetime import date
   import colab_stock_research as csr

   summary_text, recommendation_table = csr.run_pipeline()
   print(summary_text)
   recommendation_table
   ```
   - 특정 영업일 기준으로 실행하려면 `csr.run_pipeline(date(2024, 4, 12))`
     처럼 날짜를 지정합니다.

5. **보고서 활용**
   - `summary_text`: 당일 시황·경제 이벤트·미 증시 현황을 포함한 문자열입니다.
   - `recommendation_table`: 종목명, 시가·종가, 등락률, 추천 근거, 섹터·업종
     정보가 포함된 `pandas.DataFrame` 입니다.

## 모듈 개요

- `run_pipeline(as_of: date | None, config: ScreeningConfig | None)`:
  전체 분석을 수행하고 요약 문자열과 추천표를 반환합니다.
- `get_market_overview()` / `get_economic_outlook()`:
  시황 및 거시 이벤트 데이터를 수집합니다.
- `screen_candidates()`:
  재무·기술·수급 필터를 통과한 종목을 스코어링하여 추천합니다.
- `ScreeningConfig` dataclass:
  이동평균, RSI, 볼린저밴드, 수급 기간 등 필터 파라미터를 조정할 수 있습니다.

## 참고 및 한계

- `pykrx`, `FinanceDataReader`, `investpy`는 외부 데이터 제공자의 API 변경에
  영향을 받을 수 있습니다. 네트워크 오류나 데이터 제공 지연 시 일부 섹션이
  비어 있을 수 있도록 예외 처리를 해두었습니다.
- 재무 데이터는 KRX가 공시한 EPS를 활용하며, 특정 종목의 데이터가 누락된
  경우 추천 대상에서 제외될 수 있습니다.
- 실제 투자 결정 전에는 추가적인 리서치 및 리스크 관리를 수행하시기
  바랍니다.

## 로컬 실행 (선택)

Colab 이외 환경에서 사용하려면 다음 명령으로 의존성을 설치한 뒤 실행하세요.

```bash
pip install -r requirements.txt
python src/colab_stock_research.py
```

스크립트는 기본적으로 최신 영업일 기준 결과를 콘솔에 출력합니다.
