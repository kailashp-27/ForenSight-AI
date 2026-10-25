"""
Captures the report screenshots for ONE sample case ("Operation: Midnight Drop").

Usage (frontend on :5180, API on :8011, case already analysed):
    python docs/capture_screenshots.py            # everything except the live regional scan
    python docs/capture_screenshots.py --scan     # also runs ONE real regional scan (adds a draft finding)

Needs: pip install playwright   and a local Google Chrome.
"""
import sys
from playwright.sync_api import sync_playwright

BASE = "http://localhost:5180"
CASE = "80eda32aad5d4129b0f7dd4f53c897ce"      # Operation: Midnight Drop (FS-2026-A26A)
VIDEO = "b159c2c19d3f443e82ca5d874fd0cdc6"      # CCTV_ServerRm_Cam4.mp4
AUDIO = "d7cdffef4d654489adf346666ae520d9"      # Voicemail_Intercept_Ext44.mp3
OUT = "docs/screenshots/"
DO_SCAN = "--scan" in sys.argv


def seek(pg, seconds):
    pg.evaluate(f"()=>{{const v=document.querySelector('video'); v.pause(); v.currentTime={seconds};}}")
    pg.wait_for_timeout(1500)


def drag(pg, x1, y1, x2, y2):
    pg.mouse.move(x1, y1)
    pg.mouse.down()
    pg.mouse.move((x1 + x2) / 2, (y1 + y2) / 2, steps=6)
    pg.mouse.move(x2, y2, steps=6)
    pg.mouse.up()
    pg.wait_for_timeout(800)


with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome")
    pg = b.new_page(viewport={"width": 1440, "height": 1000})

    # 1 Dashboard (storyline switched to the sample case)
    pg.goto(BASE + "/"); pg.wait_for_timeout(3500)
    pg.evaluate("""()=>{const s=document.querySelector('select'); const o=[...s.options].find(o=>o.text.includes('A26A'));
                   const set=Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value').set;
                   set.call(s,o.value); s.dispatchEvent(new Event('change',{bubbles:true}));}""")
    pg.wait_for_timeout(2500)
    pg.screenshot(path=OUT + "01_dashboard.png")
    # storyline timeline with the strip collapsed (extra)
    pg.get_by_role("button", name="Collapse intelligence strip").click(); pg.wait_for_timeout(1200)
    pg.screenshot(path=OUT + "01b_dashboard_storyline.png")

    # 2 Case details
    pg.goto(f"{BASE}/cases/{CASE}"); pg.wait_for_timeout(3000)
    pg.screenshot(path=OUT + "02_case_details.png")

    # 3 Evidence upload (wizard open, CCTV/Video type chosen; nothing is uploaded)
    pg.set_viewport_size({"width": 1440, "height": 1250})
    pg.get_by_text("Upload Evidence").first.click(); pg.wait_for_timeout(1200)
    pg.get_by_text("CCTV / Video").first.click(); pg.wait_for_timeout(900)
    pg.screenshot(path=OUT + "03_evidence_upload.png")
    pg.get_by_role("button", name="Cancel").click()
    pg.set_viewport_size({"width": 1440, "height": 1000})

    # 4 Video analysis output: plate frame + extracted clues, and the YOLO detections
    pg.goto(f"{BASE}/cases/{CASE}?view={VIDEO}"); pg.wait_for_timeout(3500)
    pg.locator("button", has_text="Clues").first.click(); pg.wait_for_timeout(800)
    seek(pg, 9.708)
    pg.screenshot(path=OUT + "04_video_analysis.png")
    pg.goto(f"{BASE}/cases/{CASE}/investigation"); pg.wait_for_timeout(2500)
    pg.get_by_text("Review detections").first.click(); pg.wait_for_timeout(2500)
    pg.screenshot(path=OUT + "04b_detections.png", clip={"x": 0, "y": 330, "width": 1440, "height": 320})

    # 5 Audio transcription
    pg.goto(f"{BASE}/cases/{CASE}?view={AUDIO}"); pg.wait_for_timeout(3500)
    pg.screenshot(path=OUT + "05_audio_transcription.png")

    # 6 Workbench: region drawn around the visitor badge, verified observation on the right
    pg.set_viewport_size({"width": 1440, "height": 1250})
    pg.goto(f"{BASE}/workbench/{VIDEO}"); pg.wait_for_timeout(3500)
    seek(pg, 2.917)
    drag(pg, 715, 530, 820, 700)
    pg.get_by_text("J.VANCE Tier 2").last.scroll_into_view_if_needed(); pg.wait_for_timeout(600)
    pg.screenshot(path=OUT + "06_cctv_workbench.png")

    # 9 Event timeline across evidence (workbench lanes: audio, video, document, image)
    pg.set_viewport_size({"width": 1440, "height": 1500})
    pg.goto(f"{BASE}/workbench/{VIDEO}"); pg.wait_for_timeout(3500)
    pg.screenshot(path=OUT + "09_event_timeline.png")

    # board tabs
    pg.set_viewport_size({"width": 1440, "height": 1250})
    pg.goto(f"{BASE}/cases/{CASE}/investigation"); pg.wait_for_timeout(3000)
    pg.get_by_text("Matching clues").first.click(); pg.wait_for_timeout(1500)
    pg.get_by_text("Sector 4").first.wait_for()
    pg.mouse.click(44, 577); pg.wait_for_timeout(1200)       # chevron of the TX-88-2 plate match
    pg.screenshot(path=OUT + "07_matching_clues.png")
    pg.get_by_text("Graph", exact=True).first.click(); pg.wait_for_timeout(3500)
    pg.screenshot(path=OUT + "08_relationship_graph.png")
    pg.set_viewport_size({"width": 1440, "height": 1500})
    pg.get_by_text("Report", exact=True).first.click(); pg.wait_for_timeout(2500)
    pg.frame_locator("iframe").first.get_by_text("4. Investigator-verified findings").scroll_into_view_if_needed()
    pg.wait_for_timeout(800)
    pg.screenshot(path=OUT + "10_report.png")

    # 11 Regional scan on the number plate. DO_SCAN runs ONE real scan (adds a draft finding);
    # otherwise the reticle is drawn over the plate and the newest stored scan is shown beside it.
    pg.set_viewport_size({"width": 1440, "height": 1500})
    pg.goto(f"{BASE}/workbench/{VIDEO}"); pg.wait_for_timeout(3500)
    seek(pg, 9.708)
    pg.get_by_text("readout_text · 100%").first.click(); pg.wait_for_timeout(1200)   # jumps to that stored scan
    seek(pg, 9.708)
    drag(pg, 430, 553, 600, 612)
    if DO_SCAN:
        pg.get_by_role("button", name="Regional Scan").click()
        pg.get_by_text("Scanning").first.wait_for(timeout=10000)
        pg.get_by_text("Scanning").first.wait_for(state="detached", timeout=180000)
        pg.wait_for_timeout(1500)
    pg.screenshot(path=OUT + "11_regional_scan.png")
    b.close()
print("done")
