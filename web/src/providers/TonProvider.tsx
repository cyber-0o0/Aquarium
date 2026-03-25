'use client';

import { TonConnectUIProvider } from "@tonconnect/ui-react";
import { ReactNode } from "react";

// Disable analytics for production to avoid 400 errors on some networks
export const TonProvider = ({ children }: { children: ReactNode }) => {
  return (
    <TonConnectUIProvider 
      manifestUrl="https://raw.githubusercontent.com/ton-connect/demo-dapp-with-react-ui/master/public/tonconnect-manifest.json"
      actionsConfiguration={{
          twaReturnUrl: 'https://t.me/your_bot_user_name/app_name',
          returnStrategy: 'back'
      }}
      restoreConnection={true}
    >
      {children}
    </TonConnectUIProvider>
  );
};
