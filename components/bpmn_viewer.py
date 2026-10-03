import json
from typing import Any, Optional
import streamlit.components.v1 as components # type: ignore

def render_bpmn_html(
    bpmn_xml: str,
    tooltip_data: dict[str, Any],
    enriched_bpmn: Optional[str] = None,
    report_data: Optional[dict[str, Any]] = None
) -> None:
    """Render interactive BPMN diagram highlighting flagged nodes.
    
    Includes interactive tooltips, canvas zoom controls, and client-side
    jsPDF report generation bundled in a ZIP archive with the enriched BPMN model.
    """
    if enriched_bpmn is None:
        enriched_bpmn = bpmn_xml
    if report_data is None:
        report_data = {
            "context": "Nessun contesto specificato.",
            "timestamp": "",
            "num_violations": len(tooltip_data),
            "violations": []
        }

    safe_tooltips_json = json.dumps(tooltip_data)
    safe_xml_json = json.dumps(bpmn_xml)
    safe_enriched_json = json.dumps(enriched_bpmn)
    safe_report_json = json.dumps(report_data)

    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <link rel="stylesheet" href="https://unpkg.com/bpmn-js@17.0.2/dist/assets/bpmn-js.css">
      <script src="https://unpkg.com/bpmn-js@17.0.2/dist/bpmn-navigated-viewer.production.min.js"></script>
      <script src="https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js"></script>
      <script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
      <script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf-autotable/3.8.2/jspdf.plugin.autotable.min.js"></script>
      <style>
        @keyframes spin {{
          0% {{ transform: rotate(0deg); }}
          100% {{ transform: rotate(360deg); }}
        }}
        body {{ margin: 0; padding: 0; font-family: 'Poppins', sans-serif, -apple-system, sans-serif; }}
        #canvas {{ width: 100%; height: 530px; border: 2px solid #cbd5e1; background: #ffffff; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }}
        
        .highlight-node:not(.djs-connection) .djs-visual > :nth-child(1) {{
          stroke: #d93025 !important;
          stroke-width: 4px !important;
          fill: #fce8e6 !important;
          cursor: pointer !important;
        }}

        /* tooltip style */
        .smell-tooltip {{
          background: #ffffff;
          border-left: 4px solid #d93025;
          padding: 10px 14px;
          border-radius: 6px;
          box-shadow: 0 4px 15px rgba(0,0,0,0.15);
          font-size: 14px;
          color: #1e293b;
          white-space: nowrap;
          pointer-events: none;
          opacity: 0;
          transition: opacity 0.2s ease-in-out, transform 0.2s ease-in-out;
          transform: translateY(5px);
          z-index: 100;
        }}
        
        .smell-tooltip .badge {{
          font-size: 11px;
          background: #fce8e6;
          color: #d93025;
          padding: 2px 6px;
          border-radius: 4px;
          font-weight: bold;
          margin-right: 6px;
        }}

        [data-element-id] {{ cursor: pointer; }}
        .djs-overlay-container, .smell-overlay {{
          pointer-events: none !important;
        }}
        .smell-tooltip {{ pointer-events: none; }}
        
        /* zoom controls */
        .zoom-controls {{
          position: absolute;
          bottom: 50px;
          right: 20px;
          background: #ffffff;
          border-radius: 8px;
          box-shadow: 0 2px 10px rgba(0,0,0,0.1);
          border: 1px solid #cbd5e1;
          display: flex;
          flex-direction: column;
          overflow: hidden;
          z-index: 10;
        }}
        
        .zoom-controls button {{
          background: transparent;
          border: none;
          padding: 8px 12px;
          font-size: 18px;
          font-weight: bold;
          color: #334155;
          cursor: pointer;
          transition: background 0.2s;
        }}
        .zoom-controls button:hover {{ background: #f1f5f9; }}
        .zoom-controls button:first-child {{ border-bottom: 1px solid #cbd5e1; }}
      </style>
    </head>
    <body>
      <div id="canvas" style="position: relative;"></div>
      <div class="zoom-controls">
        <button id="btn-zoom-in" title="Zoom In">+</button>
        <button id="btn-zoom-out" title="Zoom Out">-</button>
      </div>

      <script>
        var viewer = new BpmnJS({{ 
            container: '#canvas',
            additionalModules: [
                {{ zoomScroll: [ 'value', '' ] }}
            ]
        }});
        var bpmnXML = {safe_xml_json};
        var enrichedBpmnContent = {safe_enriched_json};
        var reportData = {safe_report_json};
        var tooltipsData = {safe_tooltips_json};

        viewer.importXML(bpmnXML).then(function() {{
          var canvas = viewer.get('canvas');
          var overlays = viewer.get('overlays');
          
          document.getElementById('btn-zoom-in').addEventListener('click', function() {{
              canvas.zoom(canvas.zoom() * 1.3);
          }});
          document.getElementById('btn-zoom-out').addEventListener('click', function() {{
              canvas.zoom(canvas.zoom() * 0.7);
          }});
          
          // slight delay to ensure streamlit completes layout resizing
          setTimeout(function() {{
              canvas.zoom('fit-viewport', 'auto');
              
              // apply interactive red markers to flagged nodes
              Object.keys(tooltipsData).forEach(function(nodeId) {{
                 try {{ 
                     canvas.addMarker(nodeId, 'highlight-node'); 

                     var data = tooltipsData[nodeId];
                     var htmlContent = '<div class="smell-tooltip"><span class="badge">' + data.codice + '</span><b>' + data.nome + '</b><br><small style="color:#64748b; font-size:11px; margin-top:4px; display:block;">Clicca per scorrere ai dettagli</small></div>';
                     
                     overlays.add(nodeId, 'smell-overlay', {{
                         position: {{ bottom: 15, left: -20 }},
                         html: htmlContent
                     }});
                     
                 }} catch(e) {{ console.log("Errore rendering nodo:", nodeId, e); }}
              }});
          }}, 500);
          
          // helper to retrieve node id handling label clicks and target delegations
          function getNodeId(el) {{
              if (!el) return null;
              if (tooltipsData[el.id]) return el.id;
              if (el.labelTarget && tooltipsData[el.labelTarget.id]) return el.labelTarget.id;
              if (el.businessObject && tooltipsData[el.businessObject.id]) return el.businessObject.id;
              return null;
          }}

          // eventbus hover handling
          var eventBus = viewer.get('eventBus');
          eventBus.on('element.hover', function(e) {{
              var targetId = getNodeId(e.element);
              if(targetId) {{
                  var overlayHtml = document.querySelector('[data-container-id="' + targetId + '"] .smell-tooltip');
                  if(overlayHtml) {{
                      overlayHtml.style.opacity = '1';
                      overlayHtml.style.transform = 'translateY(0px)';
                  }}
              }}
          }});
          eventBus.on('element.out', function(e) {{
              var targetId = getNodeId(e.element);
              if(targetId) {{
                  var overlayHtml = document.querySelector('[data-container-id="' + targetId + '"] .smell-tooltip');
                  if(overlayHtml) {{
                      overlayHtml.style.opacity = '0';
                      overlayHtml.style.transform = 'translateY(5px)';
                  }}
              }}
          }});

          // click on node smoothly scrolls to corresponding detail card
          eventBus.on('element.click', function(e) {{
              var targetId = getNodeId(e.element);
              if(targetId) {{
                  try {{
                      var targetElement = window.parent.document.getElementById('card-' + targetId);
                      if (targetElement) {{
                          targetElement.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
                      }}
                  }} catch(err) {{
                      console.log("Scroll limitato.", err);
                  }}
              }}
          }});

          // formal audit pdf generation engine via jspdf
          function buildFormalPdf(report) {{
              var jsPDF = window.jspdf.jsPDF;
              var doc = new jsPDF({{ unit: 'mm', format: 'a4', orientation: 'portrait' }});
              var pageWidth = doc.internal.pageSize.getWidth();
              var pageHeight = doc.internal.pageSize.getHeight();
              var margin = 14;
              var contentWidth = pageWidth - (margin * 2);

              // page 1: title block and executive summary
              // dark blue formal top banner (#0f172a)
              doc.setFillColor(15, 23, 42);
              doc.rect(0, 0, pageWidth, 28, 'F');
              
              doc.setTextColor(56, 189, 248); // #38bdf8
              doc.setFont("helvetica", "bold");
              doc.setFontSize(8.5);
              doc.text("FRAMEWORK DI AUDITING ETICO PER PROCESSI BPMN", margin, 11);
              
              doc.setTextColor(255, 255, 255);
              doc.setFontSize(14.5);
              doc.text("Report della revisione etica del processo", margin, 20);

              var currentY = 36;

              // audit metadata table
              var statusText = report.num_violations > 0 
                  ? report.num_violations + " ethical smells individuati (non conforme)" 
                  : "Processo conforme (0 violazioni)";
              
              doc.autoTable({{
                  startY: currentY,
                  margin: {{ left: margin, right: margin }},
                  theme: 'plain',
                  styles: {{ fontSize: 8.5, cellPadding: 2.5, textColor: [30, 41, 59] }},
                  columnStyles: {{ 
                      0: {{ fontStyle: 'bold', textColor: [71, 85, 105], width: 44 }}, 
                      1: {{ width: contentWidth - 44 }} 
                  }},
                  body: [
                      ["Data e ora dell'audit:", new Date().toLocaleString('it-IT', {{ day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }})],
                      ["Modello di valutazione:", "Anthropic Claude Opus 5 (extended reasoning)"],
                      ["Esito dell'audit:", statusText],
                      ["Contesto operativo:", report.context || "Nessun contesto specificato."]
                  ]
              }});

              currentY = doc.lastAutoTable.finalY + 8;

              // section 1: executive summary of detected ethical smells
              doc.setFont("helvetica", "bold");
              doc.setFontSize(11);
              doc.setTextColor(15, 23, 42);
              doc.text("1. Sintesi esecutiva delle criticità rilevate", margin, currentY);
              
              currentY += 4;

              if (report.violations && report.violations.length > 0) {{
                  var tableRows = report.violations.map(function(v) {{
                      return [v.node_id, v.node_name, v.code + " — " + v.name, v.macro];
                  }});

                  doc.autoTable({{
                      startY: currentY,
                      margin: {{ left: margin, right: margin }},
                      head: [["ID nodo", "Elemento del processo", "Ethical smell", "Macro-principio etico violato"]],
                      body: tableRows,
                      headStyles: {{ fillColor: [15, 23, 42], textColor: [255, 255, 255], fontSize: 8, fontStyle: 'bold' }},
                      styles: {{ fontSize: 7.5, cellPadding: 2.8, textColor: [30, 41, 59] }},
                      alternateRowStyles: {{ fillColor: [248, 250, 252] }}
                  }});
              }} else {{
                  doc.autoTable({{
                      startY: currentY,
                      margin: {{ left: margin, right: margin }},
                      body: [["Nessuna violazione o anomalia etica individuata. Il flusso rispetta tutti i requisiti analizzati."]],
                      styles: {{ fontSize: 8.5, cellPadding: 4, textColor: [5, 150, 105], fillColor: [236, 253, 245] }}
                  }});
              }}

              // page 2+: violation detail cards and remediation patterns
              if (report.violations && report.violations.length > 0) {{
                  doc.addPage();
                  currentY = 20;

                  doc.setFont("helvetica", "bold");
                  doc.setFontSize(12);
                  doc.setTextColor(15, 23, 42);
                  doc.text("2. Schede di dettaglio delle violazioni etiche e mitigazioni", margin, currentY);

                  currentY += 8;

                  report.violations.forEach(function(v, idx) {{
                      var innerWidth = contentWidth - 16;

                      doc.setFont("helvetica", "normal");
                      doc.setFontSize(7.8);
                      var diagLines = doc.splitTextToSize(v.diagnosis || "Nessuna diagnosi fornita.", innerWidth);
                      var ratLines = doc.splitTextToSize(v.rationale || "Nessun razionale disponibile.", innerWidth);
                      var actLines = doc.splitTextToSize(v.action || "Nessuna azione specificata.", innerWidth);
                      var sourcesStr = (v.sources && v.sources.length) ? v.sources.join(", ") : "Nessuna fonte specifica.";
                      var srcLines = doc.splitTextToSize(sourcesStr, innerWidth);

                      var textHeight = (diagLines.length * 3.4) + (ratLines.length * 3.4) + (actLines.length * 3.4) + (srcLines.length * 3.4);
                      var cardHeight = 24 + textHeight + (4 * 7.0) + 6;

                      // automatic page break check
                      if (currentY + cardHeight > pageHeight - 16) {{
                          doc.addPage();
                          currentY = 20;
                      }}

                      // card background and border
                      doc.setDrawColor(226, 232, 240);
                      doc.setFillColor(255, 255, 255);
                      doc.roundedRect(margin, currentY, contentWidth, cardHeight, 1.5, 1.5, 'FD');

                      // vertical red accent bar
                      doc.setFillColor(217, 48, 37);
                      doc.rect(margin, currentY, 3.5, cardHeight, 'F');

                      var textX = margin + 8;
                      var lineY = currentY + 6;

                      // macro ethical principle
                      doc.setFont("helvetica", "bold");
                      doc.setFontSize(7.5);
                      doc.setTextColor(37, 99, 235);
                      doc.text("Macro-principio etico violato: " + (v.macro || "Principio non specificato"), textX, lineY);

                      // smell name and code
                      lineY += 5;
                      doc.setFontSize(10.5);
                      doc.setTextColor(15, 23, 42);
                      doc.text((v.code || "") + " — " + (v.name || "Ethical smell"), textX, lineY);

                      // process element info
                      lineY += 4.5;
                      doc.setFont("helvetica", "normal");
                      doc.setFontSize(8);
                      doc.setTextColor(100, 116, 139);
                      var nodeText = (v.node_name && v.node_name !== v.node_id)
                          ? ("Elemento del processo: " + v.node_name + "  |  ID BPMN: " + v.node_id)
                          : ("Elemento del processo: " + (v.node_name || v.node_id));
                      doc.text(nodeText, textX, lineY);

                      // horizontal divider
                      lineY += 3.5;
                      doc.setDrawColor(241, 245, 249);
                      doc.line(textX, lineY, margin + contentWidth - 8, lineY);
                      lineY += 4.5;

                      // detail fields in sentence case
                      function addField(label, lines) {{
                          doc.setFont("helvetica", "bold");
                          doc.setFontSize(7.2);
                          doc.setTextColor(71, 85, 105);
                          doc.text(label, textX, lineY);
                          lineY += 3.8;

                          doc.setFont("helvetica", "normal");
                          doc.setFontSize(7.8);
                          doc.setTextColor(30, 41, 59);
                          doc.text(lines, textX, lineY);
                          lineY += (lines.length * 3.4) + 3.2;
                      }}

                      addField("Diagnosi dell'LLM:", diagLines);
                      addField("Razionale etico:", ratLines);
                      addField("Suggerimento per la mitigazione della criticità:", actLines);
                      addField("Fonti normative e standard di riferimento:", srcLines);

                      currentY += cardHeight + 6;
                  }});
              }}

              // institutional footer across all pages
              var totalPages = doc.internal.getNumberOfPages();
              for (var i = 1; i <= totalPages; i++) {{
                  doc.setPage(i);
                  doc.setDrawColor(226, 232, 240);
                  doc.line(margin, pageHeight - 11, pageWidth - margin, pageHeight - 11);

                  doc.setFont("helvetica", "normal");
                  doc.setFontSize(7);
                  doc.setTextColor(148, 163, 184);
                  doc.text("Framework di auditing etico per processi BPMN", margin, pageHeight - 7);
                  doc.text("Pagina " + i + " di " + totalPages, pageWidth - margin, pageHeight - 7, {{ align: 'right' }});
              }}

              return doc.output('blob');
          }}

          // register download handler on parent streamlit window
          window.parent.startAnalysisDownload = function() {{
              var toast = window.parent.document.createElement('div');
              toast.style = "position: fixed; bottom: 30px; right: 30px; background: #0f172a; color: white; padding: 14px 22px; border-radius: 8px; box-shadow: 0 10px 25px rgba(0,0,0,0.3); font-family: 'Poppins', sans-serif; font-size: 14px; z-index: 999999; display: flex; align-items: center; gap: 12px;";
              toast.innerHTML = '<style>@keyframes spin {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}</style><div style="border: 3px solid #334155; border-top: 3px solid #38bdf8; border-radius: 50%; width: 18px; height: 18px; animation: spin 1s linear infinite;"></div> <span>Generazione archivio ZIP in corso...</span>';
              window.parent.document.body.appendChild(toast);

              try {{
                  var pdfBlob = buildFormalPdf(reportData);

                  var zip = new JSZip();
                  zip.file("report_revisione_etica.pdf", pdfBlob);
                  zip.file("processo_revisionato.bpmn", enrichedBpmnContent);

                  zip.generateAsync({{ type: "blob" }}).then(function(zipBlob) {{
                      var a = window.parent.document.createElement("a");
                      a.href = URL.createObjectURL(zipBlob);
                      a.download = "analisi_etica.zip";
                      a.target = "_blank"; // prevents streamlit websocket disconnection
                      window.parent.document.body.appendChild(a);
                      a.click();
                      window.parent.document.body.removeChild(a);

                      setTimeout(function() {{
                          if (toast.parentNode) toast.parentNode.removeChild(toast);
                      }}, 800);
                  }}).catch(function(zipErr) {{
                      console.error("Errore compressione ZIP:", zipErr);
                      if (toast.parentNode) toast.parentNode.removeChild(toast);
                      alert("Errore nella creazione dell'archivio ZIP.");
                  }});
              }} catch(pdfErr) {{
                  console.error("Errore generazione PDF:", pdfErr);
                  if (toast.parentNode) toast.parentNode.removeChild(toast);
                  alert("Errore nella generazione del report PDF: " + pdfErr.message);
              }}
          }};

        }});
      </script>
    </body>
    </html>
    """
    components.html(html_code, height=550)
