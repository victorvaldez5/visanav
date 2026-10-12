<template>
  <form
    class="grow mx-auto w-3/5 lg:w-2/5 min-h-0 flex flex-col justify-center gap-4"
    @submit.prevent="onSubmit"
  >
    <h3 class="mb-4 text-center text-2xl font-medium text-foreground tracking-tight">
      {{ t("auth.loginTitle") }}
    </h3>
    <Input
      v-model="email"
      :placeholder="t('auth.email')"
    />
    <Input
      v-model="password"
      type="password"
      :placeholder="t('auth.password')"
    />
    <div
      ref="turnstileEl"
      class="flex justify-center"
    />
    <Button :disabled="loading">
      {{ loading ? t("auth.loggingIn") : t("auth.logIn") }}
    </Button>
    <Alert
      v-if="error"
      variant="destructive"
    >
      <AlertTitle>{{ t("common.error") }}</AlertTitle>
      <AlertDescription>
        {{ error }}
      </AlertDescription>
    </Alert>
  </form>
</template>

<script setup lang="ts">
import {ref, useTemplateRef} from "vue";
import {useI18n} from "vue-i18n";
import {Button} from "@/components/ui/button";
import {Input} from "@/components/ui/input";
import {useAuthStore} from "@/stores/useAuthStore.ts";
import {storeToRefs} from "pinia";
import {Alert, AlertDescription, AlertTitle} from "@/components/ui/alert";
import {useTurnstile} from "@/composables/useTurnstile";

const {t} = useI18n();
const authStore = useAuthStore();
const {loading, error} = storeToRefs(authStore);
const {login} = authStore;
const email = ref("");
const password = ref("");
const turnstileEl = useTemplateRef<HTMLElement>("turnstileEl");
const {token: turnstileToken, reset: resetTurnstile} = useTurnstile(turnstileEl);

const onSubmit = async () => {
  try {
    await login(email.value, password.value, turnstileToken.value);
  } catch {
    resetTurnstile(); // token is single-use; refresh it for a retry
  }
};
</script>
