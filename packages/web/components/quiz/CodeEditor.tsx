"use client";

import { useRef, useEffect, useState } from "react";
import Editor, { type OnMount } from "@monaco-editor/react";
import type { editor } from "monaco-editor";

export interface LineAnnotation {
  line: number;
  type: "error" | "suggestion" | "praise";
  message: string;
}

interface CodeEditorProps {
  language: string;
  initialCode: string;
  maxLines?: number;
  readOnly?: boolean;
  onChange?: (code: string) => void;
  lineAnnotations?: LineAnnotation[];
}

const LINE_HEIGHT_PX = 20;

const ANNOTATION_STYLES: Record<
  LineAnnotation["type"],
  { className: string; glyphClass: string }
> = {
  error: {
    className: "code-annotation-error",
    glyphClass: "code-glyph-error",
  },
  suggestion: {
    className: "code-annotation-suggestion",
    glyphClass: "code-glyph-suggestion",
  },
  praise: {
    className: "code-annotation-praise",
    glyphClass: "code-glyph-praise",
  },
};

export function CodeEditor({
  language,
  initialCode,
  maxLines,
  readOnly = false,
  onChange,
  lineAnnotations,
}: CodeEditorProps) {
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);
  const monacoRef = useRef<Parameters<OnMount>[1] | null>(null);
  const decorationsRef = useRef<editor.IEditorDecorationsCollection | null>(null);
  const [lineCount, setLineCount] = useState(
    () => initialCode.split("\n").length,
  );

  // Compute editor height based on maxLines or content
  const displayLines = maxLines ?? Math.max(lineCount, 10);
  const editorHeight = Math.min(displayLines * LINE_HEIGHT_PX + 16, 600);

  function applyAnnotations(
    editorInstance: editor.IStandaloneCodeEditor,
    monacoInstance: Parameters<OnMount>[1],
    annotations?: LineAnnotation[],
  ) {
    const decorations: editor.IModelDeltaDecoration[] = (annotations ?? []).map(
      (ann) => {
        const styles = ANNOTATION_STYLES[ann.type];
        return {
          range: new monacoInstance.Range(ann.line, 1, ann.line, 1),
          options: {
            isWholeLine: true,
            className: styles.className,
            glyphMarginClassName: styles.glyphClass,
            hoverMessage: { value: ann.message },
            glyphMarginHoverMessage: { value: `**${ann.type}**: ${ann.message}` },
          },
        };
      },
    );

    if (decorationsRef.current) {
      decorationsRef.current.set(decorations);
    } else {
      decorationsRef.current = editorInstance.createDecorationsCollection(decorations);
    }
  }

  const handleMount: OnMount = (editorInstance, monacoInstance) => {
    editorRef.current = editorInstance;
    monacoRef.current = monacoInstance;

    // Inject annotation CSS once
    if (!document.getElementById("code-annotation-styles")) {
      const style = document.createElement("style");
      style.id = "code-annotation-styles";
      style.textContent = `
        .code-annotation-error { background: rgba(239,68,68,0.15); }
        .code-annotation-suggestion { background: rgba(234,179,8,0.15); }
        .code-annotation-praise { background: rgba(34,197,94,0.15); }
        .code-glyph-error { background: rgb(239,68,68); width: 4px !important; margin-left: 3px; border-radius: 2px; }
        .code-glyph-suggestion { background: rgb(234,179,8); width: 4px !important; margin-left: 3px; border-radius: 2px; }
        .code-glyph-praise { background: rgb(34,197,94); width: 4px !important; margin-left: 3px; border-radius: 2px; }
      `;
      document.head.appendChild(style);
    }

    applyAnnotations(editorInstance, monacoInstance, lineAnnotations);
  };

  // Re-apply annotations when they change
  useEffect(() => {
    if (editorRef.current && monacoRef.current) {
      applyAnnotations(editorRef.current, monacoRef.current, lineAnnotations);
    }
  }, [lineAnnotations]);

  return (
    <div className="rounded-md border border-border overflow-hidden">
      <Editor
        height={editorHeight}
        language={language}
        defaultValue={initialCode}
        theme="vs-dark"
        onChange={(value) => {
          const code = value ?? "";
          setLineCount(code.split("\n").length);
          onChange?.(code);
        }}
        options={{
          readOnly,
          minimap: { enabled: false },
          lineNumbers: "on",
          scrollBeyondLastLine: false,
          fontSize: 14,
          tabSize: 4,
          automaticLayout: true,
          glyphMargin: !!(lineAnnotations && lineAnnotations.length > 0),
          wordWrap: "on",
          padding: { top: 8, bottom: 8 },
        }}
        onMount={handleMount}
        loading={
          <div className="bg-zinc-900 p-4 font-mono text-sm text-zinc-300 whitespace-pre-wrap">
            {initialCode}
          </div>
        }
      />
      {maxLines != null && (
        <div className="bg-zinc-800 px-3 py-1 text-xs text-zinc-400 flex justify-end border-t border-zinc-700">
          Lines: {lineCount} / {maxLines}
        </div>
      )}
    </div>
  );
}
