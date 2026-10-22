# Initial canine vitals

The simulator uses the supplied normal-vital-sign chart for the initial resting canine baseline. These are exercise settings for the fictional patients, rather than universal anesthesia alarm limits.

| Channel | Allowed initial readings | Reference |
| --- | --- | --- |
| HR | 80–120 bpm | Supplied chart: resting dogs |
| Respiratory rate | 18–24 breaths/min | Supplied chart: resting dogs |
| Temperature | 38.1–39.1 °C | Inside the chart's 100.5–102.5 °F range |
| EtCO₂ | 35–45 mmHg | AAHA: awake patients |

The chart's Fahrenheit temperature limits convert to approximately 38.0556–39.1667 °C. The monitor displays one decimal place, so 38.1–39.1 °C keeps every displayed reading inside those limits. SpO₂ starts at 98%, and MAP varies from 88–90 mmHg across the three fictional patients; these retained simulation values are not reference ranges from the supplied chart. Mucous membrane color and skin recoil are not numerical monitor channels.

EtCO₂ (end-tidal carbon dioxide) represents CO₂ at the end of exhalation and helps assess ventilation. The [2020 AAHA anesthesia and monitoring guidelines](https://www.aaha.org/wp-content/uploads/2020/02/anesthesia_and_monitoring_guidelines_final.pdf) describe approximately 35–45 mmHg in awake patients and 40–50 mmHg (up to 55) at an appropriate surgical plane of anesthesia. Consequently, the resting baseline range must not be treated as a universal intraoperative treatment threshold. The existing hypoventilation exercise combines low RR with elevated EtCO₂ as a scripted change from baseline.

Edit `baseline_vital_ranges` in `backend/config/assessment.json` to adjust the four limits. Units are bpm, breaths/min, °C, and mmHg respectively. Limits must be finite, positive, ordered, and match the displayed precision: integers except one decimal place for temperature. Restart the backend after changing configuration.

The backend retains patient variation and small time-dependent fluctuations, then clamps rounded baseline readings to the configured limits. An active scenario's affected channels use their scripted targets; other channels retain the baseline limits. The API exposes these limits in `catalog.baseline_vital_ranges`. The Vitals panel shows the patient's readings and waveforms; reference ranges are documented here.

Run the baseline checks from `backend`:

```powershell
.\.venv\Scripts\python.exe -m unittest test_vitals
```
