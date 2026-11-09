import type { Metadata } from "next";
import { Fraunces, Noto_Naskh_Arabic, Source_Sans_3 } from "next/font/google";

import { Providers } from "@/components/Providers";
import { Shell } from "@/components/Shell";
import "./globals.css";

const display = Fraunces({ subsets: ["latin"], variable: "--font-display" });
const sans = Source_Sans_3({ subsets: ["latin", "latin-ext"], variable: "--font-sans" });
const arabic = Noto_Naskh_Arabic({
  subsets: ["arabic"],
  weight: ["500", "700"],
  variable: "--font-arabic",
});

export const metadata: Metadata = {
  title: "Qalam",
  description: "Read, summarize, translate and question documents in Arabic, French and English.",
};

const earlyLocale = `(function(){try{var l=localStorage.getItem("qalam.locale");if(l==="ar"){document.documentElement.lang="ar";document.documentElement.dir="rtl";}else if(l==="fr"||l==="en"){document.documentElement.lang=l;document.documentElement.dir="ltr";}}catch(e){}})();`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${display.variable} ${sans.variable} ${arabic.variable}`} suppressHydrationWarning>
      <body className="font-sans text-ink antialiased">
        <script dangerouslySetInnerHTML={{ __html: earlyLocale }} />
        <Providers>
          <Shell>{children}</Shell>
        </Providers>
      </body>
    </html>
  );
}
