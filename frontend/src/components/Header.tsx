import { Bell, Search, Menu } from 'lucide-react';

export default function Header() {
  return (
    <header className="fixed top-0 lg:left-[280px] right-0 z-40 bg-surface h-16 flex justify-between items-center px-6 border-b border-border-subtle backdrop-blur-md bg-surface/80">
      <div className="flex items-center gap-4 flex-1">
        <button className="lg:hidden p-2 text-on-surface hover:bg-surface-container-high rounded-lg transition-colors">
          <Menu className="w-6 h-6" />
        </button>
        <div className="hidden md:flex items-center bg-surface-container-lowest px-4 py-1.5 rounded-lg border border-border-subtle group focus-within:ring-1 focus-within:ring-primary/50 transition-all">
          <Search className="text-on-surface-variant w-4 h-4 mr-2 group-focus-within:text-primary transition-colors" />
          <input 
            className="bg-transparent border-none text-[13px] focus:ring-0 w-64 text-on-surface placeholder:text-on-surface-variant/50" 
            placeholder="Global search..." 
            type="text" 
          />
        </div>
      </div>

      <div className="flex items-center gap-4">
        <button className="p-2 text-primary hover:bg-surface-container-highest rounded-full transition-all active:scale-95 duration-100 relative group">
          <Bell className="w-5 h-5" />
          <span className="absolute top-2 right-2 w-2 h-2 bg-primary-container rounded-full border border-surface group-hover:scale-125 transition-transform"></span>
        </button>
        <div className="h-8 w-8 rounded-full overflow-hidden border border-border-subtle hover:border-primary/50 transition-colors cursor-pointer">
          <img 
            alt="User profile avatar" 
            className="h-full w-full object-cover" 
            src="https://lh3.googleusercontent.com/aida-public/AB6AXuDD5SvMU8yCFN2KODbWTmITfEuBkrtbOqkCrzWY6jHyiTkTfQsyEvH0n59P-IRu2ykLlpc-H5jQeAmTLrz05jL9weHml9LAYOqtdbgHT7JWDYyOKPikjorJqKqNUyOjmpXdmFT6Px41wrfAfkXjKl1Lvp7EEdH2MQMcIgEKpvdrkz73PKwnVexy1m5vxcURYIaMZKQJiiMP8nxlmJgvzJCec7wwjocErb8etaPkJUCTMhQ7LauUOYZJjqjQw8cclQwoMo4kx_uUiA" 
          />
        </div>
      </div>
    </header>
  );
}
