# ============================================================
#  รัน Auto-WEKA ซ้ำด้วย -metric kappa (2026-08-08)
#
#  ทำไมต้องรันซ้ำ
#  --------------
#  รอบแรก (run_autoweka.ps1) ใช้ -metric errorRate บน ARFF ดิบที่ไม่มี class weight
#  SMAC จึงค้นหาโมเดลที่ลด error rate รวมอย่างเดียว -> การทาย ICE ทั้งหมดคือคำตอบที่
#  optimal ที่สุดตาม objective นั้น (FUEL: ICE 312/316, EV 0/68, kappa -0.0059)
#  ตัวเลขที่ได้จึงเทียบกับ pipeline sklearn (class_weight="balanced" +
#  scoring="balanced_accuracy") ไม่ได้ เพราะคนละ objective
#
#  รอบนี้เปลี่ยน metric เป็น kappa ซึ่งลงโทษการทายคลาสเดียวโดยตรง
#  (kappa = 0 เมื่อโมเดลทายได้ไม่ต่างจากการเดาตามสัดส่วนคลาส)
#
#  ⚠️ เปลี่ยนจาก run_autoweka.ps1 แค่ 2 อย่างเท่านั้น: -metric และโฟลเดอร์ผลลัพธ์
#     TIME_LIMIT / MEM_LIMIT / PARALLEL / FOLDS / SEED คงเดิมทุกค่า
#     เพื่อให้เทียบกับรอบ errorRate ได้แบบ apples-to-apples
#     **ห้ามเขียนทับ autoweka_results/ ซึ่งเป็นผลรอบ errorRate ที่อ้างอิงไปแล้ว**
#
#  ⚠️ ต้องใช้ Java 8 เท่านั้น (JEP 486 ตัด SecurityManager ที่ SMAC ต้องใช้)
#
#  การใช้งาน:
#      powershell -ExecutionPolicy Bypass -File run_autoweka_kappa.ps1
#  ผลลัพธ์: analysis/autoweka_results_kappa/<ชุดข้อมูล>.txt
# ============================================================

$ErrorActionPreference = "Stop"

$JAVA = "C:\Program Files\Java\jre1.8.0_351\bin\java.exe"
$JAR  = "C:\Program Files\Weka-3-8-7\weka.jar"
$HERE = Split-Path -Parent $MyInvocation.MyCommand.Path
$ARFF = Join-Path $HERE "arff"
$OUT  = Join-Path $HERE "autoweka_results_kappa"

# ---- ค่าเดียวกับรอบ errorRate ทุกตัว (ห้ามแก้ ไม่งั้นเทียบกันไม่ได้) ----
$METRIC       = "kappa"
$TIME_LIMIT   = 25     # นาที ต่อการเทรน 1 ครั้ง -> ~4.6 ชม. ต่อชุด
$MEM_LIMIT    = 1536   # MB ต่อ SMAC worker
$PARALLEL     = 2
$FOLDS        = 10
$SEED         = 123

$SETS = @("cardss_buy", "cardss_buy_balanced", "cardss_fuel", "cardss_fuel_balanced")

if (-not (Test-Path $JAVA)) { throw "ไม่พบ Java 8 ที่ $JAVA" }
if (-not (Test-Path $OUT))  { New-Item -ItemType Directory -Path $OUT | Out-Null }

$env:_JAVA_OPTIONS = ""

Write-Output "เริ่ม $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  metric=$METRIC"
Write-Output "timeLimit=$TIME_LIMIT min/build x $($FOLDS+1) builds -> ~$([math]::Round($TIME_LIMIT*($FOLDS+1)/60,1)) ชม. ต่อชุด (รันพร้อมกันทั้ง 4)"
Write-Output ""

$procs = @()
foreach ($s in $SETS) {
    $in = Join-Path $ARFF "$s.arff"
    if (-not (Test-Path $in)) { throw "ไม่พบ $in — รัน export_arff.py ก่อน" }

    # ต้องใส่ quote เองรอบ path ที่มีช่องว่าง ("Program Files")
    $jargs = @(
        "-Xmx2g", "-cp", "`"$JAR`"", "weka.Run",
        "weka.classifiers.meta.AutoWEKAClassifier",
        "-t", "`"$in`"", "-x", $FOLDS, "-s", 1,
        "-timeLimit", $TIME_LIMIT, "-memLimit", $MEM_LIMIT,
        "-parallelRuns", $PARALLEL, "-seed", $SEED,
        "-metric", $METRIC
    )
    $p = Start-Process -FilePath $JAVA -ArgumentList $jargs -PassThru -NoNewWindow `
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
    $f = Join-Path $OUT "$($x.Name).txt"
    $acc = Select-String -Path $f -Pattern "Correctly Classified" -ErrorAction SilentlyContinue | Select-Object -Last 1
    $kap = Select-String -Path $f -Pattern "Kappa statistic"      -ErrorAction SilentlyContinue | Select-Object -Last 1
    if ($null -eq $acc) {
        $e = Get-Content (Join-Path $OUT "$($x.Name).err.txt") -TotalCount 1 -ErrorAction SilentlyContinue
        $msg = if ($e) { "ERROR: $e" } else { "ไม่มีผลลัพธ์" }
    } else {
        $msg = "$($acc.Line.Trim())  |  $($kap.Line.Trim())"
    }
    Write-Output ("  {0,-24} exit={1}  {2}" -f $x.Name, $x.Proc.ExitCode, $msg)
}
