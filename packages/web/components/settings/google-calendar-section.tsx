"use client";

import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { GoogleIcon } from "@/components/icons/google";
import { Button } from "@/components/ui/button";
import { Calendar } from "lucide-react";

export function GoogleCalendarSection() {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Calendar className="h-5 w-5" />
          Google Calendar
        </CardTitle>
        <CardDescription>
          Sync your assessment due dates to Google Calendar
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex items-center gap-3">
          <Button variant="outline" disabled>
            <GoogleIcon className="mr-2 h-4 w-4" />
            Connect Google Calendar
          </Button>
          <Badge variant="secondary" className="text-xs">
            Coming Soon!
          </Badge>
        </div>
      </CardContent>
    </Card>
  );
}
