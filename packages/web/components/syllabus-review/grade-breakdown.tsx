"use client";

import { useState } from "react";
import { AlertTriangle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableFooter,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ConfidenceIndicator } from "./confidence-indicator";
import { cn } from "@/lib/utils";
import {
  getConfidenceLevel,
  getConfidenceColor,
  type GradeComponent,
} from "@/types/extraction";

interface GradeBreakdownProps {
  components: GradeComponent[];
  onChange: (
    index: number,
    field: "name" | "weight_percent" | "drop_policy",
    value: string | number | null,
  ) => void;
  hideConfidence?: boolean;
}

type EditingCell = { row: number; col: string } | null;

export function GradeBreakdown({ components, onChange, hideConfidence }: GradeBreakdownProps) {
  const [editingCell, setEditingCell] = useState<EditingCell>(null);
  const [editValue, setEditValue] = useState("");

  const totalWeight = components.reduce((sum, c) => {
    const w = c.weight_percent.value;
    return sum + (typeof w === "number" ? w : 0);
  }, 0);

  const weightOff = Math.abs(totalWeight - 100) > 1;

  function startEdit(row: number, col: string, currentValue: string) {
    setEditingCell({ row, col });
    setEditValue(currentValue);
  }

  function commitEdit(row: number, col: "name" | "weight_percent" | "drop_policy") {
    setEditingCell(null);
    if (col === "weight_percent") {
      const num = parseFloat(editValue);
      onChange(row, col, isNaN(num) ? null : num);
    } else {
      onChange(row, col, editValue);
    }
  }

  function handleKeyDown(
    e: React.KeyboardEvent,
    row: number,
    col: "name" | "weight_percent" | "drop_policy",
  ) {
    if (e.key === "Enter") commitEdit(row, col);
    if (e.key === "Escape") setEditingCell(null);
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <CardTitle className="text-base">Grade Breakdown</CardTitle>
          {weightOff && (
            <Badge variant="outline" className="text-red-700 border-red-300 bg-red-50">
              <AlertTriangle className="mr-1 h-3 w-3" />
              Weights sum to {totalWeight.toFixed(1)}%
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Component</TableHead>
              <TableHead className="w-24">Weight %</TableHead>
              <TableHead>Drop Policy</TableHead>
              {!hideConfidence && <TableHead className="w-28">Confidence</TableHead>}
            </TableRow>
          </TableHeader>
          <TableBody>
            {components.map((comp, i) => {
              const level = getConfidenceLevel(comp.weight_percent.confidence);
              const rowColor = hideConfidence ? "" : getConfidenceColor(level);
              return (
                <TableRow key={i} className={cn(!hideConfidence && "border-l-4", rowColor)}>
                  {/* Name */}
                  <TableCell>
                    {editingCell?.row === i && editingCell?.col === "name" ? (
                      <Input
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        onBlur={() => commitEdit(i, "name")}
                        onKeyDown={(e) => handleKeyDown(e, i, "name")}
                        autoFocus
                        className="h-7 text-sm"
                      />
                    ) : (
                      <span
                        className="cursor-pointer hover:underline"
                        onClick={() =>
                          startEdit(i, "name", String(comp.name.value ?? ""))
                        }
                      >
                        {comp.name.value ?? "—"}
                      </span>
                    )}
                  </TableCell>
                  {/* Weight */}
                  <TableCell>
                    {editingCell?.row === i && editingCell?.col === "weight" ? (
                      <Input
                        type="number"
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        onBlur={() => commitEdit(i, "weight_percent")}
                        onKeyDown={(e) => handleKeyDown(e, i, "weight_percent")}
                        autoFocus
                        className="h-7 text-sm w-20"
                      />
                    ) : (
                      <span
                        className="cursor-pointer hover:underline"
                        onClick={() =>
                          startEdit(
                            i,
                            "weight",
                            String(comp.weight_percent.value ?? ""),
                          )
                        }
                      >
                        {comp.weight_percent.value != null
                          ? `${comp.weight_percent.value}%`
                          : "—"}
                      </span>
                    )}
                  </TableCell>
                  {/* Drop Policy */}
                  <TableCell>
                    {editingCell?.row === i && editingCell?.col === "drop" ? (
                      <Input
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        onBlur={() => commitEdit(i, "drop_policy")}
                        onKeyDown={(e) => handleKeyDown(e, i, "drop_policy")}
                        autoFocus
                        className="h-7 text-sm"
                      />
                    ) : (
                      <span
                        className="cursor-pointer text-muted-foreground hover:underline"
                        onClick={() =>
                          startEdit(
                            i,
                            "drop",
                            String(comp.drop_policy?.value ?? ""),
                          )
                        }
                      >
                        {comp.drop_policy?.value ?? "None"}
                      </span>
                    )}
                  </TableCell>
                  {/* Confidence */}
                  {!hideConfidence && (
                    <TableCell>
                      <ConfidenceIndicator
                        confidence={comp.weight_percent.confidence}
                        sourceText={comp.weight_percent.source_text}
                      />
                    </TableCell>
                  )}
                </TableRow>
              );
            })}
          </TableBody>
          <TableFooter>
            <TableRow>
              <TableCell className="font-medium">Total</TableCell>
              <TableCell
                className={cn("font-medium", weightOff && "text-red-600")}
              >
                {totalWeight.toFixed(1)}%
              </TableCell>
              <TableCell />
              {!hideConfidence && <TableCell />}
            </TableRow>
          </TableFooter>
        </Table>
      </CardContent>
    </Card>
  );
}
