<template>
  <form
    class="grow mx-auto w-3/5 lg:w-2/5 min-h-0 flex flex-col justify-center gap-4"
    @submit.prevent="onSubmit"
  >
    <h3 class="mb-4 text-center text-2xl font-medium text-foreground tracking-tight">
      {{ t("auth.registerTitle") }}
    </h3>
    <FormField
      v-slot="{ componentField }"
      v-model="values.email"
      name="email"
      validate-on-change
      validate-on-blur
    >
      <FormItem>
        <FormLabel>{{ t("auth.email") }}</FormLabel>
        <FormControl>
          <Input
            type="email"
            v-bind="componentField"
          />
        </FormControl>
        <FormMessage />
      </FormItem>
    </FormField>

    <FormField
      v-slot="{ componentField }"
      v-model="values.password"
      name="password"
      validate-on-change
      validate-on-blur
    >
      <FormItem>
        <FormLabel>{{ t("auth.password") }}</FormLabel>
        <FormControl>
          <Input
            type="password"
            v-bind="componentField"
          />
        </FormControl>
        <FormMessage />
      </FormItem>
    </FormField>

    <FormField
      v-slot="{ componentField }"
      v-model="values.password2"
      name="password2"
      validate-on-change
      validate-on-blur
    >
      <FormItem>
        <FormLabel>{{ t("auth.verifyPassword") }}</FormLabel>
        <FormControl>
          <Input
            type="password"
            v-bind="componentField"
          />
        </FormControl>
        <FormMessage />
      </FormItem>
    </FormField>

    <div
      ref="turnstileEl"
      class="flex justify-center"
    />

    <Button :disabled="loading">
      {{ loading ? t("auth.creatingAccount") : t("auth.createAccount") }}
    </Button>
  </form>
</template>

<script setup lang="ts">
import {useTemplateRef} from "vue";
import {useI18n} from "vue-i18n";
import {Button} from "@/components/ui/button";
import {Input} from "@/components/ui/input";
import {useAuthStore} from "@/stores/useAuthStore.ts";
import {storeToRefs} from "pinia";
import {toTypedSchema} from "@vee-validate/zod";
import {z} from "zod";
import {useForm} from "vee-validate";
import {FormControl, FormField, FormItem, FormLabel, FormMessage} from "@/components/ui/form";
import {useTurnstile} from "@/composables/useTurnstile";

interface RegisterForm {
  email: string;
  password: string;
  password2: string | null;
}

const {t} = useI18n();
const authStore = useAuthStore();
const {loading, error} = storeToRefs(authStore);
const {register} = authStore;

const formSchema = toTypedSchema(z.object({
  email: z.string().nonempty(t("auth.required")).email(t("auth.invalidEmail")),
  password: z.string().min(8, t("auth.passwordMin")),
  password2: z.string().min(8, t("auth.passwordMin")),
}).refine((data) => data.password === data.password2, {
  message: t("auth.passwordsMismatch"),
  path: ["password2"],
}));

const {values, handleSubmit, setErrors} = useForm<RegisterForm>({
  validationSchema: formSchema,
});

const turnstileEl = useTemplateRef<HTMLElement>("turnstileEl");
const {token: turnstileToken, reset: resetTurnstile} = useTurnstile(turnstileEl);

const onSubmit = handleSubmit(async (submitValues) => {
  try {
    if (submitValues.password !== submitValues.password2) {
      error.value = t("auth.passwordsMismatch");
      return
    }
    await register(submitValues.email, submitValues.password, submitValues.password2, turnstileToken.value);
  } catch (e: any) {
    resetTurnstile(); // token is single-use; refresh it for a retry
    console.error(e.response?.data);
    setErrors({
      email: e.response?.data?.email,
      password: e.response?.data?.password
    });
  }
});
</script>
