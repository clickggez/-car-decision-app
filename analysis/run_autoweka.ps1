# ============================================================
#  รัน Auto-WEKA บนชุดข้อมูล CarDSS ทั้ง 4 ชุด (2026-08-08)
#
#  วัตถุประสงค์: หาหลักฐาน "ข้ามเครื่องมือ" ว่าความแม่นยำชนเพดานสารสนเทศจริง
#  โดยให้ Auto-WEKA ค้นหาอัตโนมัติทั้งพื้นที่ (อัลกอริทึม x ไฮเปอร์พารามิเตอร์
#  x วิธีคัดฟีเจอร์) แทนการเลือกเองแบบมีอคติ
#
#  ⚠️ ต้องใช้ Java 8 เท่านั้น
#     Java 24+ ตัด SecurityManager ทิ้งถาวร (JEP 486) แต่ SMAC ซึ่งเป็นตัวค้นหา
#     ของ Auto-WEKA เรียก System.setSecurityManager() -> ตายทันทีที่เริ่ม
#     Java 25 ที่มากับ WEKA 3.8.7 จึงใช้ไม่ได้
#
#  การใช้งาน:
#      powershell -ExecutionPolicy Bypass -File run_autoweka.ps1
#  ผลลัพธ์: analysis/autoweka_results/<ชุดข้อมูล>.txt
# ============================================================

$ErrorActionPreference = "Stop"

$JAVA = "C:\Program Files\Java\jre1.8.0_351\bin\java.exe"
$JAR  = "C:\Program Files\Weka-3-8-7\weka.jar"
$HERE = Split-Path -Parent $MyInvocation.MyCommand.Path
$ARFF = Join-Path $HERE "arff"
$OUT  = Join-Path $HERE "autoweka_results"

# ---- งบประมาณการค้นหา ----
# TIME_LIMIT คือเวลาค้นหา "ต่อการเทรน 1 ครั้ง" — 10-fold CV เทรน 11 ครั้ง
# (10 fold + 1 ครั้งบนข้อมูลเต็ม) เวลารวมต่อชุด = TIME_LIMIT x 11
$TIME_LIMIT   = 25     # นาที -> ~4.6 ชม. ต่อชุด
$MEM_LIMIT    = 1536   # MB ต่อ SMAC worker
$PARALLEL     = 2      # SMAC runs ขนานต่อชุด
$FOLDS        = 10
$SEED         = 123
# 4 ชุด x PARALLEL 2 = 8 worker x 1.5GB = ~12GB จาก RAM 31.7GB

$SETS = @("cardss_buy", "cardss_buy_balanced", "cardss_fuel", "cardss_fuel_balanced")

if (-not (Test-Path $JAVA)) { throw "ไม่พบ Java 8 ที่ $JAVA" }
if (-not (Test-Path $OUT))  { New-Item -ItemType Directory -Path $OUT | Out-Null }

# ล้าง _JAVA_OPTIONS (ตัวเปิดของ WEKA ตั้ง --add-opens ไว้ ซึ่ง Java 8 ไม่รู้จัก)
$env:_JAVA_OPTIONS = ""

Write-Output "เริ่ม $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Output "timeLimit=$TIME_LIMIT min/build x $($FOLDS+1) builds -> ~$([math]::Round($TIME_LIMIT*($FOLDS+1)/60,1)) ชม. ต่อชุด (รันพร้อมกันทั้ง 4)"
Write-Output ""

$procs = @()
foreach ($s in $SETS) {
    $in = Join-Path $ARFF "$s.arff"
    if (-not (Test-Path $in)) { throw "ไม่พบ $in — รัน export_arff.py ก่อน" }

    # ต้องใส่ quote เองรอบ path ที่มีช่องว่าง ("Program Files") — Start-Process
    # ส่ง -ArgumentList แบบ array โดยไม่ใส่ quote ให้ ทำให้ path ถูกตัดกลางทาง
    $args = @(
        "-Xmx2g", "-cp", "`"$JAR`"", "weka.Run",
        "weka.classifiers.meta.AutoWEKAClassifier",
        "-t", "`"$in`"", "-x", $FOLDS, "-s", 1,
        "-timeLimit", $TIME_LIMIT, "-memLimit", $MEM_LIMIT,
        "-parallelRuns", $PARALLEL, "-seed", $SEED,
        "-metric", "errorRate"
    )
    $p = Start-Process -FilePath $JAVA -ArgumentList $args -PassThru -NoNewWindow `
            -RedirectStandardOutput (Join-Path $OUT "$s.txt") `
            -RedirectStandardError  (Join-Path $OUT "$s.err.txt")
    $procs += [pscustomobject]@{ Name = $s; Proc = $p }
    Write-Output "  เริ่ม $s (PID $($p.Id))"
}

Write-Output ""
Write-Output "รอทั้ง 4 ชุดเสร็จ..."
$procs | ForEach-Object { $_.Proc.WaitForExit() }

Write-Output ""
Write-Output "เสร็จ $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
foreach ($x in $procs) {
    $line = Select-String -Path (Join-Path $OUT "$($x.Name).txt") `
                          -Pattern "Correctly Classified" -ErrorAction SilentlyContinue |
            Select-Object -Last 1
    if ($null -eq $line) {
        # รันไม่สำเร็จ — ดึงบรรทัดแรกของ stderr มาแสดงแทน จะได้รู้สาเหตุทันที
        $e = Get-Content (Join-Path $OUT "$($x.Name).err.txt") -TotalCount 1 -ErrorAction SilentlyContinue
        $msg = if ($e) { "ERROR: $e" } else { "ไม่มีผลลัพธ์" }
    } else {
        $msg = $line.Line.Trim()
    }
    Write-Output ("  {0,-24} exit={1}  {2}" -f $x.Name, $x.Proc.ExitCode, $msg)
}
