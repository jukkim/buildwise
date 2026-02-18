FROM nrel/energyplus:24.1.0

# EnergyPlus 24.1 공식 이미지 기반
# https://hub.docker.com/r/nrel/energyplus

# 작업 디렉토리
WORKDIR /opt/workdir

# 날씨 데이터 디렉토리
RUN mkdir -p /opt/weather

# 한국 10도시 EPW 파일 복사
COPY weather/KOR_*.epw /opt/weather/

# 헬스체크
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD energyplus --version || exit 1

# 기본 실행 (실제로는 Celery worker가 호출)
ENTRYPOINT ["energyplus"]
CMD ["--help"]
