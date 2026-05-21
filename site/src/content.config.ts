import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

const posts = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/posts' }),
  schema: z.object({
    title: z.string(),
    date: z.coerce.date(),
    categories: z.array(z.string()).optional().default([]),
    tags: z.array(z.string()).optional().default([]),
    coverImage: z.string().optional(),
    draft: z.boolean().optional().default(false),
    description: z.string().optional(),
    lastModified: z.coerce.date().optional(),
    // Structured data for AI schema markup
    faqItems: z.array(z.object({ question: z.string(), answer: z.string() })).optional(),
    howToSteps: z.array(z.object({ name: z.string(), text: z.string() })).optional(),
    listItems: z.array(z.object({ name: z.string(), url: z.string().optional() })).optional(),
  }),
});

export const collections = { posts };
