"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { BookOpen, Menu, X } from "lucide-react";
import { Button } from "@/components/ui/button";

const NAV_LINKS = [
  { label: "Features", href: "#features" },
  { label: "How It Works", href: "#how" },
  { label: "Stack", href: "/stack" },
] as const;

interface NavbarProps {
  activeLink?: string;
}

export function Navbar({ activeLink }: NavbarProps) {
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    function onScroll() {
      setScrolled(window.scrollY > 50);
    }
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <nav
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        scrolled
          ? "backdrop-blur-lg bg-white/90 border-b border-border shadow-sm"
          : "bg-transparent"
      }`}
    >
      <div className="max-w-6xl mx-auto px-6 flex items-center justify-between h-16">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2.5">
          <div className="flex h-[34px] w-[34px] items-center justify-center rounded-lg bg-primary">
            <BookOpen className="h-4 w-4 text-primary-foreground" />
          </div>
          <span className="text-lg font-[800] tracking-tight text-foreground">
            LectureLink
          </span>
        </Link>

        {/* Desktop nav */}
        <div className="hidden md:flex items-center gap-1">
          {NAV_LINKS.map((link) => {
            const isActive = activeLink === link.href;
            const isExternal = !link.href.startsWith("#");
            const Comp = isExternal ? Link : "a";
            return (
              <Comp
                key={link.href}
                href={link.href}
                className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
                  isActive
                    ? "text-foreground bg-muted font-medium"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted"
                }`}
              >
                {link.label}
              </Comp>
            );
          })}
        </div>

        {/* CTA + mobile toggle */}
        <div className="flex items-center gap-3">
          <Button
            asChild
            className="hidden sm:inline-flex bg-primary text-primary-foreground rounded-lg px-5 py-2 text-sm font-semibold"
          >
            <Link href="/login">Try the Demo</Link>
          </Button>
          <button
            className="md:hidden p-2 rounded-lg hover:bg-muted transition-colors"
            onClick={() => setMobileOpen(!mobileOpen)}
            aria-label="Toggle menu"
          >
            {mobileOpen ? (
              <X className="h-5 w-5" />
            ) : (
              <Menu className="h-5 w-5" />
            )}
          </button>
        </div>
      </div>

      {/* Mobile menu */}
      {mobileOpen && (
        <div className="md:hidden border-t border-border bg-white/95 backdrop-blur-lg px-6 pb-4 pt-2">
          {NAV_LINKS.map((link) => {
            const isExternal = !link.href.startsWith("#");
            const Comp = isExternal ? Link : "a";
            return (
              <Comp
                key={link.href}
                href={link.href}
                className="block py-2.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
                onClick={() => setMobileOpen(false)}
              >
                {link.label}
              </Comp>
            );
          })}
          <Button asChild className="w-full mt-2" size="sm">
            <Link href="/login">Try the Demo</Link>
          </Button>
        </div>
      )}
    </nav>
  );
}
