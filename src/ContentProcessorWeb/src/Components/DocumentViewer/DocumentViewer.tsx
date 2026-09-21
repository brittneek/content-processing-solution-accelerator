// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

/**
 * Renders an inline document viewer that selects the correct embed strategy
 * (Office Online, native PDF, image zoom, TIFF, or generic iframe) based on
 * the file’s MIME type.
 */

import React, { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { TIFFViewer } from 'react-tiff';
import { Button } from "@fluentui/react-components";
import { Document, Page, pdfjs } from "react-pdf";

import Zoom from "react-medium-image-zoom";
import "react-medium-image-zoom/dist/styles.css";

import './DocumentViewer.styles.scss';
import { SourceEvidenceSelection } from "../../store/slices/rightPanelSlice";

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
    "pdfjs-dist/build/pdf.worker.min.mjs",
    import.meta.url,
).toString();

/** Metadata describing the document to be rendered. */
interface DocumentMetadata {
  /** MIME type of the document (e.g. "application/pdf"). */
  readonly mimeType: string;
}

/** Props for the {@link DocumentViewer} component. */
interface DocumentViewerProps {
  /** Optional CSS class name applied to the outer container. */
  readonly className?: string;
  /** Document metadata containing at least the MIME type. */
  readonly metadata?: DocumentMetadata;
  /** Pre-signed URL (with SAS token) to the document blob. */
  readonly urlWithSasToken: string | undefined;
  /** Key used to force iframe re-mount when the document changes. */
  readonly iframeKey: number;
  /** Selected compliance evidence to display on a PDF page. */
  readonly selectedEvidence?: SourceEvidenceSelection | null;
  /** Clears the active source highlight and returns to the standard viewer. */
  readonly onClearEvidence?: () => void;
}

/**
 * Selects and renders the appropriate viewer for the given document based on MIME type.
 */
const DocumentViewer: React.FC<DocumentViewerProps> = ({
    className,
    metadata,
    urlWithSasToken,
    iframeKey,
    selectedEvidence,
    onClearEvidence,
}) => {
    const { t } = useTranslation();
    const [imgError, setImageError] = useState(false);
    const [pageWidth, setPageWidth] = useState(600);
    const [pageCount, setPageCount] = useState(0);
    const [visiblePage, setVisiblePage] = useState(1);
    const pdfContainerRef = useRef<HTMLDivElement | null>(null);

    useEffect(() => {
        setImageError(false)
    }, [urlWithSasToken])

    useEffect(() => {
        if (selectedEvidence) {
            setVisiblePage(selectedEvidence.pageNumber);
        }
    }, [selectedEvidence]);

    useEffect(() => {
        if (!selectedEvidence || !pdfContainerRef.current) return;
        const observer = new ResizeObserver(([entry]) => {
            setPageWidth(Math.max(240, Math.floor(entry.contentRect.width - 24)));
        });
        observer.observe(pdfContainerRef.current);
        return () => observer.disconnect();
    }, [selectedEvidence]);

    const getHighlightColor = () => {
        if (selectedEvidence?.status === "pass") return "rgba(16, 124, 16, 0.28)";
        if (selectedEvidence?.status === "error") return "rgba(247, 99, 12, 0.3)";
        return "rgba(196, 43, 28, 0.32)";
    };

    const getHighlightedPdf = () => {
        if (!selectedEvidence || !urlWithSasToken) return null;
        const pageRegions = selectedEvidence.regions.filter(
            (region) => region.page_number === visiblePage,
        );
        return (
            <div className="pdfEvidenceViewer">
                <div className="pdfEvidenceToolbar">
                    <Button
                        size="small"
                        disabled={visiblePage <= 1}
                        onClick={() => setVisiblePage((page) => page - 1)}
                    >
                        Previous
                    </Button>
                    <span>
                        {selectedEvidence.entityName} — page {visiblePage}
                        {pageCount > 0 ? ` of ${pageCount}` : ""}
                    </span>
                    <Button
                        size="small"
                        disabled={pageCount === 0 || visiblePage >= pageCount}
                        onClick={() => setVisiblePage((page) => page + 1)}
                    >
                        Next
                    </Button>
                    <Button size="small" appearance="subtle" onClick={onClearEvidence}>
                        Close highlight
                    </Button>
                </div>
                <div className="pdfEvidenceScroll" ref={pdfContainerRef}>
                    <Document
                        file={urlWithSasToken}
                        onLoadSuccess={({ numPages }) => setPageCount(numPages)}
                        onLoadError={() => setImageError(true)}
                        loading={<p>Loading source page...</p>}
                    >
                        <div className="pdfEvidencePage">
                            <Page
                                pageNumber={visiblePage}
                                width={pageWidth}
                                renderAnnotationLayer={false}
                                renderTextLayer={false}
                            />
                            <svg
                                className="pdfEvidenceOverlay"
                                viewBox="0 0 1 1"
                                preserveAspectRatio="none"
                                aria-label={`Source highlight for ${selectedEvidence.entityName}`}
                            >
                                {pageRegions.map((region, index) => (
                                    <polygon
                                        key={`${region.page_number}-${index}`}
                                        points={region.polygon
                                            .map((point) => `${point.x},${point.y}`)
                                            .join(" ")}
                                        fill={getHighlightColor()}
                                        stroke={getHighlightColor().replace(/0\.\d+\)/, "0.9)")}
                                        strokeWidth="0.003"
                                    />
                                ))}
                            </svg>
                        </div>
                    </Document>
                </div>
            </div>
        );
    };

    const getContentComponent = () => {
        if (!metadata || !urlWithSasToken) {
            return <div className={"noDataDocContainer"}><p>{t("components.document.none", "No document available")}</p></div>;
        }

        switch (metadata.mimeType) {
            case "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
            case "application/vnd.ms-excel.sheet.macroEnabled.12":
            case "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            case "application/vnd.openxmlformats-officedocument.presentationml.presentation": {
                return (
                    <iframe
                        key={iframeKey}
                        src={`https://view.officeapps.live.com/op/embed.aspx?src=${encodeURIComponent(
                            urlWithSasToken
                        )}`}
                        width="100%"
                        height="100%"
                        title={getTitle(metadata.mimeType)}
                    />
                );
            }
            case "application/pdf": {
                if (selectedEvidence) {
                    return getHighlightedPdf();
                }
                return <iframe style={{ border: '1px solid lightgray' }} title="PDF Viewer" key={iframeKey} src={urlWithSasToken.toString()} width="100%" height="100%" />;
            }
            case "image/jpeg":
            case "image/png":
            case "image/gif":
            case "image/bmp":
            case "image/svg+xml": {
                return <div className="imageContainer">
                    <Zoom>
                        <img src={urlWithSasToken} alt={"Document"} onError={() => setImageError(true)} width="100%" height="100%" className="document-image" />
                    </Zoom>
                </div>;
            }
            case "image/tiff": {
                return (
                    <div
                        style={{
                            width: "100%",
                            height: "100%",
                            objectFit: "contain",
                            overflowX: "scroll",
                            overflowY: "auto",
                        }}
                    >
                        <TIFFViewer tiff={urlWithSasToken} style={{ width: 100, height: 100, objectFit: "contain" }} />
                    </div>
                );
            }

            default: {
                return (
                    <iframe key={iframeKey} src={urlWithSasToken} width="100%" height="100%" title="Doc visualizer" />
                );
            }
        }
    };

    const getTitle = (mimeType: string) => {
        switch (mimeType) {
            case "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
            case "application/vnd.ms-excel.sheet.macroEnabled.12":
                return "Excel viewer";
            case "application/vnd.openxmlformats-officedocument.presentationml.presentation":
                return "PowerPoint viewer";
            case "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                return "Word viewer";
            case "application/pdf":
                return "PDF Viewer";
            default:
                return "Doc visualizer";
        }
    };

    return (
        <div className={`${className} ${imgError ? 'imageErrorContainer' : ''}`}>
            {imgError ?
                <div className={"invalidImagePopup"}>
                    <span className="imgEH">We can't open this file</span>
                    <p className="imgCtn">Something went wrong.</p>
                </div>
                : getContentComponent()
            }
        </div>
    );
}

export default DocumentViewer;