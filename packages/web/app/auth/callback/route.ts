import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { NextResponse, type NextRequest } from "next/server";

export async function GET(request: NextRequest) {
  const { searchParams, origin } = request.nextUrl;
  const code = searchParams.get("code");

  if (!code) {
    return NextResponse.redirect(`${origin}/login?error=missing_code`);
  }

  const cookieStore = await cookies();

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll();
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value, options }) =>
            cookieStore.set(name, value, options),
          );
        },
      },
    },
  );

  const { data, error } = await supabase.auth.exchangeCodeForSession(code);

  if (error || !data.session) {
    return NextResponse.redirect(`${origin}/login?error=auth_failed`);
  }

  // If we got Google OAuth tokens, store them in the backend for calendar sync
  const providerToken = data.session.provider_token;
  const providerRefreshToken = data.session.provider_refresh_token;

  if (providerToken) {
    const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    try {
      await fetch(`${apiBase}/api/google/tokens`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${data.session.access_token}`,
        },
        body: JSON.stringify({
          access_token: providerToken,
          refresh_token: providerRefreshToken ?? null,
        }),
      });
    } catch {
      // Non-fatal — user can reconnect later from Settings
    }
  }

  return NextResponse.redirect(`${origin}/dashboard`);
}
