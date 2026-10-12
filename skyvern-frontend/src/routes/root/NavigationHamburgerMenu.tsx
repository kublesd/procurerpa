import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import {
  Drawer,
  DrawerContent,
  DrawerDescription,
  DrawerHeader,
  DrawerTitle,
  DrawerTrigger,
} from "@/components/ui/drawer";
import { HamburgerMenuIcon } from "@radix-ui/react-icons";
import { SidebarContent } from "./SidebarContent";
import * as VisuallyHidden from "@radix-ui/react-visually-hidden";

function NavigationHamburgerMenu() {
  const [open, setOpen] = useState(false);
  const { pathname } = useLocation();
  useEffect(() => setOpen(false), [pathname]);
  return (
    <div className="block lg:hidden">
      <Drawer direction="left" open={open} onOpenChange={setOpen}>
        <DrawerTrigger asChild>
          <button type="button" aria-label="打开导航" className="rounded p-1">
            <HamburgerMenuIcon className="size-6" />
          </button>
        </DrawerTrigger>
        <DrawerContent className="bottom-2 left-2 top-2 mt-0 h-full w-64 rounded border-0">
          <VisuallyHidden.Root>
            <DrawerHeader>
              <DrawerTitle>ProcureRPA</DrawerTitle>
              <DrawerDescription>
                ProcureRPA Enterprise Navigation
              </DrawerDescription>
            </DrawerHeader>
          </VisuallyHidden.Root>
          <SidebarContent />
        </DrawerContent>
      </Drawer>
    </div>
  );
}

export { NavigationHamburgerMenu };
