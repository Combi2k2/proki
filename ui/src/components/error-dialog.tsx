// What went wrong, told in a dialog over the page. One the person can resolve (a name already used, a change refused) is closed with OK; one they
// can't (Proki isn't answering) has no button and can't be dismissed, and goes by itself when the error clears.

import {
  AlertDialog, AlertDialogAction, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog"

const UNRESOLVABLE = /failed to fetch|networkerror|load failed|timed out|connection (refused|reset|lost|failed)|unreachable|not running|no response/i

/** Whether the person can do nothing about `message`: Proki itself isn't answering. */
export const unresolvable = (message: string) => UNRESOLVABLE.test(message)

/** `message` told over the page; `onClose` clears it (called by OK, and by Escape or a click around it, for one that can be resolved). `stuck`: it
 * can't be, whatever it says. */
export function ErrorDialog({ message, stuck = unresolvable(message), onClose }: { message: string; stuck?: boolean; onClose?: () => void }) {
  return (
    <AlertDialog open onOpenChange={(open) => !open && !stuck && onClose?.()}>
      <AlertDialogContent size="sm" onEscapeKeyDown={(e) => stuck && e.preventDefault()}>
        <AlertDialogHeader>
          <AlertDialogTitle>{stuck ? "Proki isn't answering" : "That didn't work"}</AlertDialogTitle>
          <AlertDialogDescription className="break-words">{message}{/[.!?]$/.test(message) ? "" : "."} {stuck ? "Check that Proki is running. This closes when it reconnects." : "Change what it names, then try again."}</AlertDialogDescription>
        </AlertDialogHeader>
        {!stuck && <AlertDialogFooter><AlertDialogAction onClick={onClose}>OK</AlertDialogAction></AlertDialogFooter>}
      </AlertDialogContent>
    </AlertDialog>
  )
}
