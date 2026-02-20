"use client";

import {
  Play,
  Pause,
  SkipBack,
  SkipForward,
  Volume2,
  VolumeX,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { formatTimestamp } from "@/lib/format";
import type { AudioPlayerState } from "@/components/lectures/hooks/use-audio-player";
import { PLAYBACK_RATES } from "@/components/lectures/hooks/use-audio-player";

interface AudioPlayerBarProps {
  audioUrl: string;
  audioRef: React.RefObject<HTMLAudioElement | null>;
  controls: Omit<AudioPlayerState, "audioRef">;
}

export function AudioPlayerBar({
  audioUrl,
  audioRef,
  controls,
}: AudioPlayerBarProps) {
  const {
    isPlaying,
    currentTime,
    duration,
    playbackRate,
    volume,
    isMuted,
    toggle,
    skip,
    seek,
    setPlaybackRate,
    setVolume,
    toggleMute,
  } = controls;

  return (
    <>
      {/* Hidden audio element */}
      <audio ref={audioRef} src={audioUrl} preload="metadata" />

      {/* Player bar */}
      <div className="fixed bottom-0 inset-x-0 z-50 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80 border-t">
        <div className="flex items-center gap-2 px-4 py-2 max-w-screen-2xl mx-auto">
          {/* Skip back */}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => skip(-10)}
            className="h-8 w-8 p-0 shrink-0"
            title="Skip back 10s"
          >
            <SkipBack className="h-4 w-4" />
          </Button>

          {/* Play/Pause */}
          <Button
            variant="default"
            size="sm"
            onClick={toggle}
            className="h-9 w-9 p-0 rounded-full shrink-0"
            title={isPlaying ? "Pause" : "Play"}
          >
            {isPlaying ? (
              <Pause className="h-4 w-4" />
            ) : (
              <Play className="h-4 w-4 ml-0.5" />
            )}
          </Button>

          {/* Skip forward */}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => skip(10)}
            className="h-8 w-8 p-0 shrink-0"
            title="Skip forward 10s"
          >
            <SkipForward className="h-4 w-4" />
          </Button>

          {/* Current time */}
          <span className="text-xs font-mono text-muted-foreground w-10 text-right shrink-0">
            {formatTimestamp(currentTime)}
          </span>

          {/* Seek bar */}
          <Slider
            value={[currentTime]}
            min={0}
            max={duration || 100}
            step={1}
            onValueChange={([val]) => seek(val)}
            className="flex-1 mx-2"
          />

          {/* Duration */}
          <span className="text-xs font-mono text-muted-foreground w-10 shrink-0">
            {formatTimestamp(duration)}
          </span>

          {/* Speed selector */}
          <Select
            value={String(playbackRate)}
            onValueChange={(v) => setPlaybackRate(Number(v))}
          >
            <SelectTrigger className="h-7 w-16 text-xs shrink-0">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {PLAYBACK_RATES.map((rate) => (
                <SelectItem key={rate} value={String(rate)} className="text-xs">
                  {rate}x
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {/* Volume */}
          <div className="hidden sm:flex items-center gap-1 shrink-0">
            <Button
              variant="ghost"
              size="sm"
              onClick={toggleMute}
              className="h-8 w-8 p-0"
              title={isMuted ? "Unmute" : "Mute"}
            >
              {isMuted || volume === 0 ? (
                <VolumeX className="h-4 w-4" />
              ) : (
                <Volume2 className="h-4 w-4" />
              )}
            </Button>
            <Slider
              value={[isMuted ? 0 : volume]}
              min={0}
              max={1}
              step={0.05}
              onValueChange={([val]) => setVolume(val)}
              className="w-20"
            />
          </div>
        </div>
      </div>
    </>
  );
}
