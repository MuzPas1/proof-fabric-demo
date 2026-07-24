import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { LogIn, LogOut } from "lucide-react";
import {
  fetchAuth0Config,
  fetchAuth0Session,
  loginWithAuth0,
  logoutAuth0,
} from "@/lib/auth0";

export function UserMenu() {
  const [enabled, setEnabled] = useState(false);
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      const cfg = await fetchAuth0Config();
      if (!alive) return;
      setEnabled(!!cfg.enabled);
      if (cfg.enabled) {
        const s = await fetchAuth0Session();
        if (!alive) return;
        setUser(s && s.authenticated ? s.user : null);
      }
      setReady(true);
    })();
    return () => {
      alive = false;
    };
  }, []);

  if (!enabled || !ready) return null;

  if (!user) {
    return (
      <Button
        size="sm"
        variant="outline"
        onClick={() => loginWithAuth0()}
        data-testid="auth0-login-btn"
        className="border-slate-200 text-slate-700 hover:bg-slate-50 font-medium"
      >
        <LogIn className="w-4 h-4 mr-1.5" />
        Log in with Auth0
      </Button>
    );
  }

  const initial = (user.name || user.email || "U").trim().charAt(0).toUpperCase();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          className="flex items-center gap-2 rounded-full pl-1 pr-2 py-1 hover:bg-slate-100 transition-colors"
          data-testid="auth0-profile-btn"
        >
          <Avatar className="w-8 h-8">
            <AvatarImage src={user.picture} alt={user.name || "user"} />
            <AvatarFallback className="bg-blue-600 text-white text-xs font-semibold">
              {initial}
            </AvatarFallback>
          </Avatar>
          <span className="hidden sm:inline text-sm font-medium text-slate-700 max-w-[120px] truncate">
            {user.name || user.email}
          </span>
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56 bg-white border-slate-200">
        <DropdownMenuLabel className="pb-1">
          <div
            className="text-sm font-semibold text-slate-900 truncate"
            data-testid="auth0-user-name"
          >
            {user.name || "Signed in"}
          </div>
          <div
            className="text-xs font-normal text-slate-500 truncate"
            data-testid="auth0-user-email"
          >
            {user.email}
          </div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          onClick={() => logoutAuth0()}
          data-testid="auth0-logout-btn"
          className="text-red-600 focus:text-red-700 focus:bg-red-50 cursor-pointer"
        >
          <LogOut className="w-4 h-4 mr-2" />
          Log out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
